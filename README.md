# asyncproc
Simplifies the creation of asynchronous, multiprocess, and multithreaded code

# TODO
## Create arguments & functions objects
1. Use the `inspect.signature().parameters` function to find out how many arguments are needed and their names - refer to this as `N`.
2. For each argument, the `create_argument` function needs the following info:
  - From the user:
    - Argument name (str)
    - Argument value
    - Argument type
    - Which instances for a function it should be used (list, set, or tuple)
3. For each function, the `create_function` function needs the following info:
  - From the user:
    - Function name (str)
    - Pointer to the function (typing.Callable)
    - Number of instances to run (int)
  - From the function pointer:
    - Arguments by name and expected values (dictionary)

## Relationship between processes, threads, and functions
- The general idea is to allow the user to specify:
  - The number of CPU physical and logical cores to use in total
  - The number of CPU physical and logical cores to use per process
  - The number of CPU physical and logical cores to use per thread
  - The number of CPU physical and logical cores to use per function
  - The number of processes to run in total
  - The number of threads to run in total
  - The number of functions to run in total
  - The number of threads to run per process
    - If thread-per-process is 1 then do not have to manually create a thread
  - The number of functions to run per process
  - The number of functions to run per thread
  - Which functions to run
  - What arguments to use for what functions

- Assuming 4 physical cores and 8 logical cores:
  - How to specify 6 processes on to which cores:
    - Manually -> list/set/tuple of ints:
      - Index specifies core, value identifies how many processes
      - IE: `[2, 0, 1, 2, 0, 1, 0, 0]`
      - Advantage is variable is easy to set and work with
      - Disadvantages:
        - Only specifies info for processes-per-core
        - Does not specify how many threads per process

## Core/Process/Thread/Function/Argument object idea
```python
cores = {
    "0": {
        "processes": 2,
        "threads": 3,
        "functions": {
            "func1": {
                "call": func1,
                "arguments": {
                    "arg1": {
                        "value": 1,
                        "type": int
                    },
                    "arg2": {
                        "value": "test",
                        "type": str
                    }
                }
            },
            "func2": {...}
        },
    },
    "1": {...}
}
```
