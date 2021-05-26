# asyncproc
Simplifies the creation of asynchronous, multiprocess, and multithreaded code

# TODO
1. Use the `inspect.signature().parameters` function to find out how many arguments are needed and their names - refer to this as `N`.
2. For each argument, the `create_argument` function needs the following info:
  - From the user:
    - Argument name (str)
    - Argument value
    - Argument type
    - Which instances for a function it should be used (list, set, or tuple)
3. For each function, the `create_argument` function needs the following info:
  - From the user:
    - Function name (str)
    - Pointer to the function (typing.Callable)
    - Number of instances to run (int)
  - From the function pointer:
    - Arguments by name and expected values (dictionary)
