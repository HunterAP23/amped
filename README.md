# AMPED
__A__synchronous __M__ulti-__P__ool __E__xecution __D__irector

Simplifies the creation & management of asynchronous thread & process pools.

# Summary
AMPED is a cross-platform process and thread pool management library. It makes
the steps required for creating thread and process pools much simpler, adds new
features such as pool management & pool-nesting, provides thread-safe data
transfer methods, and allows for granular control over CPU core assignment of
individual pools.

# Example Uses
## Creating a Process Pool for CPU-bound tasks
```python
from amped import amped

def doubler(n):
  return n * 2

handler = amped()
handler.create_pool(pool_type="process", group="process-group-one", name="first")
```

## Using a Process Pool
```python
ints = [1, 2, 3, 4]
print("ints is {}".format(ints))
for i in ints:
  print(handler.submit_pool("process-group-one", "first", doubler, i))
```
```
[1, 2, 3, 4]
2
4
6
8
```

## Using the Map function
```python
ints = [1, 2, 3, 4]
print("ints is {}".format(ints))
  print(handler.submit_map("process-group-one", "first", doubler, ints))
```

## Creating a Thread Pools for I/O-bound Tasks
