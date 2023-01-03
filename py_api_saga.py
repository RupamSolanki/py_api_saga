import types
from concurrent.futures import ThreadPoolExecutor
from functools import partial


class SagaAssembler(object):
    """
    Saga assembler to create saga.
    """

    def __init__(self, retry_attempts=None):

        if retry_attempts and not (
            isinstance(retry_attempts, int) or isinstance(retry_attempts, float)
        ):
            raise SagaAssembler.SagaException(
                f"`retry_attempts` cannot be {type(retry_attempts)} type. Integer type is required."
            )
        self.__retry_attempts = retry_attempts or 1
        self.__operations = []
        self.__saga_results = []

    class SagaException(Exception):
        """
        Raised when an operation action failed.
        """

        def __init__(
            self,
            operation_error,
            operation_name=None,
            compensation_success_result=None,
            compensation_error=None,
        ):
            self.operation_name = operation_name
            self.operation_error = operation_error
            self.compensation_success_result = compensation_success_result
            self.compensation_errors = compensation_error

    class __SagaThreadExecutor(ThreadPoolExecutor):
        """
        Saga thread pool Executor.
        """

        def submit(self, *args, func_index, func_name):
            return {
                "function_index": func_index,
                "function": super().submit(*args),
                "function_name": func_name,
            }

    class __SagaThreadException(Exception):
        """
        Raised when a thread operation action failed.
        """

        def __init__(self, success_results, failed_results):
            self.success_results = success_results
            self.failed_results = failed_results

    @staticmethod
    def saga(retry_attempts=None):
        """
        create SagaAssembler instance.
        """

        return SagaAssembler(retry_attempts=retry_attempts)

    def __retry_operation(self, func):
        """
        Perform and retry operation.
        """

        error = None
        for _ in range(self.__retry_attempts):
            try:
                func.func.saga_results = self.__saga_results
                response = func()
                self.__saga_results.append(response)
            except Exception as err:
                error = err
            else:
                return response
        else:
            raise error

    def __check_operation(self, arg):
        """
        Validate operation/compensation.
        """

        if hasattr(arg, "__iter__"):
            if isinstance(arg[0], types.FunctionType):
                return partial(*arg)
        else:
            if isinstance(arg, types.FunctionType):
                return partial(arg)
        raise self.SagaException("Please add function in operation argument.")

    def operation(self, *args):
        """
        Add an operation action and a corresponding compensation.
        """

        if not args:
            raise self.SagaException("Operation can not be empty")
        elif len(args) > 2:
            raise self.SagaException(
                "Only two operations (action, compensation) are allowed."
            )
        self.__operations.append(tuple([self.__check_operation(arg) for arg in args]))
        return self

    def __check_available_operations(self):
        """
        Check operation availability.
        """

        if not self.__operations:
            raise self.SagaException("Set operation first to execute the saga.")

    def orchestrator_execute(self):
        """
        Executes a series of Operation Actions.
        If one of the operation exception raises, the compensation for all previous operations
        are executed in reverse order.
        While executing compensations possible Exceptions are recorded and raised wrapped in a SagaException once all
        compensations have been executed.
        """

        self.__check_available_operations()
        response = []
        for operation_index in range(len(self.__operations)):
            try:
                response.append(
                    self.__retry_operation(self.__operations[operation_index][0])
                )
            except Exception as operation_error:
                (
                    compensation_success_result,
                    compensation_errors,
                ) = self.__execute_orchestrator_compensation(operation_index)
                raise self.SagaException(
                    operation_error,
                    self.__operations[operation_index][0].func.__name__,
                    compensation_success_result,
                    compensation_errors,
                )
        return response

    def __execute_orchestrator_compensation(self, last_operation_index):
        """
        Execute the compensation by last operation index.
        """

        compensation_success_result = []
        compensation_exceptions = []
        for compensation_index in range(last_operation_index - 1, -1, -1):
            try:
                if len(self.__operations[compensation_index]):
                    compensation_success_result.append(
                        self.__operations[compensation_index][-1]()
                    )
            except Exception as compensation_error:
                compensation_exceptions.append(str(compensation_error))
        return compensation_success_result or None, compensation_exceptions or None

    def __prepare_thread_result(self, threads):
        """
        Prepare threads result.
        """

        success = []
        success_index = []
        errors = []
        for thread in threads:
            try:
                success.append(thread.get("function").result())
                success_index.append(thread.get("function_index"))
            except Exception as error:
                errors.append(
                    {
                        "function_index": thread["function_index"],
                        "function_name": thread["function_name"],
                        "error": error,
                    }
                )
        if errors:
            raise self.__SagaThreadException(
                success_results=success_index, failed_results=errors
            )
        return success

    def choreography_execute(self):
        """
        Executes a series of Operation Actions by python threads.
        If one of the operation exception raises, the compensation for all successes operations
        are executed.
        While executing compensations possible Exceptions are recorded and raised wrapped in a SagaException once all
        compensations have been executed.
        """
        try:
            self.__check_available_operations()
            with self.__SagaThreadExecutor(
                max_workers=len(self.__operations)
            ) as pool_executor:
                return self.__prepare_thread_result(
                    [
                        pool_executor.submit(
                            partial(
                                self.__retry_operation,
                                self.__operations[operation_index][0],
                            ),
                            func_index=operation_index,
                            func_name=self.__operations[operation_index][
                                0
                            ].func.__name__,
                        )
                        for operation_index in range(len(self.__operations))
                    ]
                )

        except self.__SagaThreadException as operation_error:
            (
                compensation_success_result,
                compensation_errors,
            ) = self.__execute_choreography_compensation(
                operation_error.success_results
            )
            raise self.SagaException(
                operation_error.failed_results[0]["error"],
                operation_error.failed_results[0]["function_name"],
                compensation_success_result,
                compensation_errors,
            )

    def __execute_choreography_compensation(self, success_index):
        """
        Execute the compensation on succeed operation index.
        """

        compensation_success_result = []
        compensation_exceptions = []
        with self.__SagaThreadExecutor(len(self.__operations)) as pool_executor:
            compensation_threads = [
                pool_executor.submit(
                    self.__operations[compensation_index][-1],
                    func_index=compensation_index,
                    func_name=self.__operations[compensation_index][-1].func.__name__,
                )
                for compensation_index in success_index
                if len(self.__operations[compensation_index]) == 2
            ]
            for thread in compensation_threads:
                try:
                    compensation_success_result.append(thread.get("function").result())
                except Exception as error:
                    compensation_exceptions.append(str(error))
        return compensation_success_result or None, compensation_exceptions or None
