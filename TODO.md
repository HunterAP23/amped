# TODO
## Create arguments & functions objects
1. [ ] Test performance of different implementations
    - [ ] Make sure existing functions work correctly with assigning CPU affinity:
      - [ ] `submit` vs `apply` and `apply_async`
      - [ ] `map` vs `map` and `map_async`
    - [ ] Recreate `multiprocessing`'s functions for `concurrent.futures` pool objects:
      - [ ] `imap`
      - [ ] `imap_unordered`
      - [ ] `starmap` / `starmap_async`
  - [ ] Queues vs Lists for affinity
    - [ ] List vs `random.choice` of list
  - [ ] Looping vs List for getting results from functions
  - [ ] Using a wrapper function for setting/resetting affinity vs building it directly into the `submit`/`apply` functions
  2. [ ] Validate function arguments:
    - [ ] Use the `inspect.signature().parameters` function to find out how many arguments are needed and their names
    - [ ] Validate for initializer, if provided
    - [ ] Validate for main function given for pool
  3. [ ] Add variable for threadpools to allow creating X as many threads as specified by the affinity variable

# Test Variations
## No multithreading/multiprocessing
- [ ] Loop comprehension
- [ ] List comprehension

## ThreadPoolExecutor
- [ ] Submit / Apply
  - [ ] No affinity handling (OS handles picking cores/threads)
    - [ ] Loop comprehension
    - [ ] List comprehension
  - [ ] Use wrapper affinity handler
    - [ ] Affinity stored in list
      - [ ] Get affinity element with `list.pop()`
        - [ ] Loop comprehension
        - [ ] List comprehension
      - [ ] Get affinity element with `random.choice`
        - [ ] Loop comprehension
        - [ ] List comprehension
    - [ ] Affinity stored in queue
      - [ ] Get affinity element with `queue.get()`
        - [ ] Loop comprehension
        - [ ] List comprehension
      - [ ] Get affinity element with `random.choice`
        - [ ] Loop comprehension
        - [ ] List comprehension
- [ ] Map
  - [ ] No affinity handling (OS handles picking cores/threads)
    - [ ] Loop comprehension
    - [ ] List comprehension
  - [ ] Use wrapper affinity handler
    - [ ] Affinity stored in list
      - [ ] Get affinity element with `list.pop()`
        - [ ] Loop comprehension
        - [ ] List comprehension
      - [ ] Get affinity element with `random.choice`
        - [ ] Loop comprehension
        - [ ] List comprehension
    - [ ] Affinity stored in queue
      - [ ] Get affinity element with `queue.get()`
        - [ ] Loop comprehension
        - [ ] List comprehension
      - [ ] Get affinity element with `random.choice`
        - [ ] Loop comprehension
        - [ ] List comprehension

## ProcessPoolExecutor
- [ ] Submit / Apply
  - [ ] No affinity handling (OS handles picking cores/threads)
    - [ ] Loop comprehension
    - [ ] List comprehension
  - [ ] Use wrapper affinity handler
    - [ ] Affinity stored in list
      - [ ] Get affinity element with `list.pop()`
        - [ ] Loop comprehension
        - [ ] List comprehension
      - [ ] Get affinity element with `random.choice`
        - [ ] Loop comprehension
        - [ ] List comprehension
    - [ ] Affinity stored in queue
      - [ ] Get affinity element with `queue.get()`
        - [ ] Loop comprehension
        - [ ] List comprehension
      - [ ] Get affinity element with `random.choice`
        - [ ] Loop comprehension
        - [ ] List comprehension
- [ ] Map
  - [ ] No affinity handling (OS handles picking cores/threads)
    - [ ] Loop comprehension
    - [ ] List comprehension
  - [ ] Use wrapper affinity handler
    - [ ] Affinity stored in list
      - [ ] Get affinity element with `list.pop()`
        - [ ] Loop comprehension
        - [ ] List comprehension
      - [ ] Get affinity element with `random.choice`
        - [ ] Loop comprehension
        - [ ] List comprehension
    - [ ] Affinity stored in queue
      - [ ] Get affinity element with `queue.get()`
        - [ ] Loop comprehension
        - [ ] List comprehension
      - [ ] Get affinity element with `random.choice`
        - [ ] Loop comprehension
        - [ ] List comprehension

# COMPLETED
[x] Make sure affinity for pool is the same or a subset of the overall affinity
