[![Github](https://github.com/eadwinCode/django-ninja-extra/workflows/Test/badge.svg)](https://github.com/RupamSolanki/api-saga)
[![Python version](https://img.shields.io/pypi/pyversions/django-ninja-extra.svg)](https://www.python.org/downloads/)

# PY API SAGA

**PY API SAGA** is a complete class-based fashion of building saga pattern for microservices. It offers both narrative
patterns `Orchestration-Based Saga` and `Choreography-Based Saga`. To execute saga operations use the following method.

- orchestrator_execute
- choreography_execute

**orchestrator_execute** Every transition is carried out one by one. If exception arises, all prior operations
will be compensated in the reversed order. All the operation responses are contained in the result list and the results
are arranged in the same sequence as the Saga operations.

**choreography_execute** Every transition is carried out concurrently, and no operation is dependent on any other
process. Hence, multithreading is used an if an error occurs in any of the operation process all the succeeded
operations will be compensated.

While executing compensations possible Exceptions are recorded and raised wrapped in a SagaException once all
compensations have been executed.

**Key features:**

- **Easy**: Designed to be easy to use and intuitive.
- **Fast to code**: Type hints and automatic docs lets you focus only on business logic.
- **Framework friendly**: Since it developed with standard Python, so it can simply implement with python based
  frameworks like Django and Flask.
- **Retry operation attempts**: Retry an operation action again if it fails.

---

### Requirements

- Python >= 3.6

## Installation

```
pip install py_api_saga
```

After installation, import `SagaAssembler` from `py_api_saga`


### Declartion
The saga operation contains only two function operation action and compensation. The action and compensation are 
 by two ways.
- when operation has arguments then pass the function along with in a tuple.
- When function is without argument then simply pass the function name.

**Example**

```python
from py_api_saga import SagaAssembler

...
# Operation with argument functions 
SagaAssembler.saga().operation((function_name, arg_1, arg_2),
                               (compensation_function_name, arg_1)).orchestrator_execute()
...

# Operation without argument functions
SagaAssembler.saga().operation(function_name, compensation_function_name).orchestrator_execute()

```

## Usage

Simple example

```Python
import json

import requests


def update_product_state(state):
    #function to update the state in product service.
    url = "https://host/productService/product/123/"
    # updat e product state from 'in_stock' to 'sold_out' 
    response = requests.post(url=url,data=json.dumps({"state":state}))
    if response != 200:
        raise Exception(response.error)
    return response
    
def update_shipping_state(shipping_state):
    #function to update the state in shipping service.
    url = "https://host/shippingService/product/123/shipping/"
    # update shipping state to 'ready_to_dispatch'
    response = requests.post(url=url, data=json.dumps({"state": shipping_state}))
    if response != 200:
        raise Exception(response.error)
    return response
   

```

Now build saga as given below:

```Python
...
from py_api_saga import SagaAssembler

...
try:
    result = SagaAssembler.saga().operation((update_product_state, 'sold_out'),(update_product_state, 'in_stock')).operation((update_shipping_state, 'ready_to_dispatch')).choreography_execute()
except SagaAssembler.SagaException as exception:
  return str(exception.operation_error)
...
```

### Advanced saga usage

The prior operation result can be accessed inside the operation function when using `orchestrator_execute`.

**Example**
```python

def function_name(args):
    # access previous functions outcomes.
    prior_results = function_name.saga_results
    ...
```

### Advanced saga Exception handling

When an error occurs in saga execution it can be handled using `SagaException`. The SagaException provides error as well
as information to track error function and compensation results.

**Exmaple**
```python
...
except SagaAssembler.SagaException as exception:
    # Error
    exception.operation_error
    # Function name responsible for the error.
    exception.operation_name    
    # Compensation success result list.
    exception.compensation_success_result
    # Error list that occurs when compensation is executed.
    exception.compensation_errors                                
```

