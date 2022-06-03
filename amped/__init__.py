# Process related
import asyncio
import collections as col
import concurrent.futures as cf
import errno
import functools as ft
import inspect
import logging as lg
import multiprocessing as mp
import multiprocessing.pool as mpp
import multiprocessing.synchronize as sync
import os
import platform as plat
import random as rand
import re
import sched
import shlex
import subprocess as sp
import sys
import threading
import time
import traceback
from collections.abc import Generator, Iterable, Mapping, MutableSet, Sequence, Set
from concurrent.futures import ProcessPoolExecutor as ppe
from concurrent.futures import ThreadPoolExecutor as tpe
from concurrent.futures import _base
from concurrent.futures.process import _WorkItem as _WorkItem_Process
from concurrent.futures.thread import _WorkItem as _WorkItem_Thread
from contextlib import contextmanager
from multiprocessing.context import BaseContext
from typing import Any, Callable, Literal, Optional, Tuple, Type, TypeVar, Union

import psutil

_global_shutdown = False
_global_shutdown_lock = threading.Lock()
_shutdown = False


def _check_instance(var: Any, name: str, types: Union[Type, tuple[Type, ...]], can_be_none=True) -> None:
    if not isinstance(var, types) and var is None and not can_be_none:
        raise TypeError("'{}' object is not of type {}.".format(name, types))


# def _check_callable(func: Callable, name: str, can_be_none=True) -> None:
#     if not callable(func) and func is not None:
#         raise TypeError("Function '{}' object is not callable.".format(name))


# def _announce_initialization(proc):
#     @ft.wraps(proc)
#     def do_thing(*args, **kwargs):
#         msg = "Initializing {}"
#         print(msg.format(kwargs["name"]))
#         return proc(*args, **kwargs)
#     return do_thing

################################################################################
class cf_common:
    def _submit_wrapper(self, *args, wrapped_func: Callable, choice: bool = False, **kwargs):
        my_core = None
        try:
            # affinity_type = affinity._token.typeid
            if self._affinity_type == "list":
                while len(self._affinity) == 0:
                    continue
                while True:
                    try:
                        if self._choice:
                            my_core = self._affinity.pop(self._affinity.index(rand.choice(self._affinity)))
                        else:
                            my_core = self._affinity.pop()
                        break
                    # Normally this could throw ValueError or IndexError exceptions
                    # But we can just retry until we get what we need
                    except Exception:
                        continue
            else:
                my_core = self._affinity.get()
        except AttributeError as ae:
            raise AttributeError(ae)

        psutil.Process().cpu_affinity([my_core])
        ret = wrapped_func(*args, **kwargs)
        if self._affinity_type == "list":
            self._affinity.append(my_core)
        else:
            self._affinity.task_done()
            self._affinity.put(my_core)
        psutil.Process().cpu_affinity(list(self._affinity))
        return ret


################################################################################
class _amped_process_pool_cf(cf_common):
    def __init__(
        self,
        name: str,
        affinity: list[int],
        affinity_type: Literal["queue", "list"] = "queue",
        choice: bool = False,
        initializer: Optional[Callable[..., None]] = None,
        initargs: Tuple[Any, ...] = (),
        mp_context: Optional[BaseContext] = None,
    ):
        self._name = name
        self._affinity = affinity
        self._affinity_type = affinity_type
        self._max_workers = len(affinity)
        self._choice = choice
        self._initializer = initializer
        self._initargs = initargs
        self._mp_context = mp_context

        self._manager = mp.Manager()
        if affinity_type == "list":
            self._affinity_data = self._manager.list(affinity)
        else:
            self._affinity_data = self._manager.Queue(self._max_workers)
            for i in affinity:
                self._affinity_data.put(i)

        if self._initializer is None:
            # super().__init__(max_workers=self._max_workers, mp_context=self._mp_context)
            self._parent = ppe(max_workers=self._max_workers, mp_context=self._mp_context)
        else:
            # super().__init__(
            self._parent = ppe(
                max_workers=self._max_workers,
                mp_context=self._mp_context,
                initializer=self._initializer,
                initargs=self._initargs,
            )

    # def submit_wrapper(self, fn: Callable, *args: Any, **kwargs: Any) -> cf.Future:
    # return super().submit(
    # return self._parent.submit(
    #     fn=_submit_wrapper,
    #     *args,
    #     wrapped_func=fn,
    #     affinity=self._affinity_data,
    #     choice=self._choice,
    #     **kwargs
    # )

    def submit(self, fn: Callable, *args: Any, **kwargs: Any) -> cf.Future:
        return super()._submit_wrapper(*args, wrapped_func=fn, **kwargs)

    def map_wrapper(self, fn, *iterables: Any, timeout: Optional[float] = None, chunksize: int = 1):
        if timeout is not None:
            end_time = timeout + time.monotonic()

        fs = [self.submit_wrapper(fn, *args) for args in zip(*iterables)]

        def result_iterator():
            try:
                fs.reverse()
                while fs:
                    while len(fs) == 0:
                        continue
                    if timeout is None:
                        yield fs.pop().result()
                    else:
                        yield fs.pop().result(end_time - time.monotonic())
            finally:
                for future in fs:
                    future.cancel()

        return result_iterator()

    def shutdown(self, wait=True, cancel_futures=False):
        # return super().shutdown(wait=wait, cancel_futures=cancel_futures)
        return self._parent.shutdown(wait=wait, cancel_futures=cancel_futures)


################################################################################
class _amped_thread_pool_cf(cf_common):
    def __init__(
        self,
        name: str,
        affinity: list[int],
        affinity_type: Literal["queue", "list"] = "queue",
        choice: bool = False,
        initializer: Optional[Callable[..., None]] = None,
        initargs: Tuple[Any, ...] = (),
        mp_context: Optional[mp.context.SpawnContext] = None,
    ) -> None:
        self._name = name
        self._affinity = affinity
        self._max_workers = len(affinity)
        self._choice = choice
        self._initializer = initializer
        self._initargs = initargs

        self._manager = mp.Manager()
        if affinity_type == "list":
            self._affinity_data = self._manager.list(self._affinity)
        else:
            self._affinity_data = self._manager.Queue(len(self._affinity))
            for i in affinity:
                self._affinity_data.put(i)

        if self._initializer is None:
            # super().__init__(
            self._parent = tpe(max_workers=self._max_workers, thread_name_prefix=self._name)
        else:
            # super().__init__(
            self._parent = tpe(
                max_workers=self._max_workers,
                thread_name_prefix=self._name,
                initializer=self._initializer,
                initargs=self._initargs,
            )

    def submit_wrapper(self, fn, *args, **kwargs) -> cf.Future:
        # return super().submit(
        return self._parent.submit(fn=_submit_wrapper, *args, wrapped_func=fn, affinity=self._affinity_data, choice=self._choice, **kwargs)

    def apply(self, fn, *args, **kwargs) -> cf.Future:
        return self.submit(fn, *args, **kwargs)

    def map_wrapper(self, fn, *iterables: Iterable[Any], timeout: Optional[float] = None, chunksize: int = 1):
        if timeout is not None:
            end_time = timeout + time.monotonic()

        fs = [self.submit_wrapper(fn, *args) for args in zip(*iterables)]

        def result_iterator():
            try:
                fs.reverse()
                while fs:
                    while len(fs) == 0:
                        continue
                    if timeout is None:
                        yield fs.pop().result()
                    else:
                        yield fs.pop().result(end_time - time.monotonic())
            finally:
                for future in fs:
                    future.cancel()

        return result_iterator()

    def shutdown(self, wait=True, cancel_futures=False):
        # return super().shutdown(wait=wait, cancel_futures=cancel_futures)
        return self._parent.shutdown(wait=wait, cancel_futures=cancel_futures)


################################################################################
# class _amped_process_pool_mp:
#     def __init__(
#         self,
#         name: str,
#         affinity: list[int],
#         affinity_type: Literal["queue", "list"] = "queue",
#         choice: bool = False,
#         initializer: Optional[Callable[..., None]] = None,
#         initargs: Tuple[Any, ...] = (),
#         maxtasksperchild: Optional[int] = None,
#         mp_context: Optional[mp.context.SpawnContext] = None,
#     ) -> None:
#         self._name = name
#         self._affinity = affinity
#         self._max_workers = len(affinity)
#         self._choice = choice
#         self._initializer = initializer
#         self._initargs = initargs
#         self._mp_context = mp_context
#
#         self._manager = mp.Manager()
#         if affinity_type == "list":
#             self._affinity_data = self._manager.list(self._affinity)
#         else:
#             self._affinity_data = self._manager.Queue(len(self._affinity))
#             for i in affinity:
#                 self._affinity_data.put(i)
#
#         if self._initializer is None:
#             # super().__init__(processes=self._max_workers, context=self._mp_context)
#             self._parent = mpp.Pool(
#                 processes=self._max_workers, context=self._mp_context
#             )
#         else:
#             # super().__init__(
#             self._parent = mpp.Pool(
#                 processes=self._max_workers,
#                 initializer=self._initializer,
#                 initargs=self._initargs,
#                 context=self._mp_context,
#             )
#
#     def apply_wrapper(self, fn, *args: Any, **kwargs: Any):
#         kw = {}
#         kw["wrapped_func"] = fn
#         kw["affinity"] = self._affinity_data
#         kw["choice"] = self._choice
#         # return super().apply(func=_submit_wrapper, *args, **kw, **kwargs)
#         return self._parent.apply(func=_submit_wrapper, *args, **kw, **kwargs)
#
#     def map_wrapper(
#         self, fn, *iterables: Any, timeout: Optional[float] = None, chunksize: int = 1
#     ):
#         if timeout is not None:
#             end_time = timeout + time.monotonic()
#
#         fs = [self.apply_wrapper(fn, *args) for args in zip(*iterables)]
#
#         def result_iterator():
#             try:
#                 fs.reverse()
#                 while fs:
#                     while len(fs) == 0:
#                         continue
#                     if timeout is None:
#                         yield fs.pop().result()
#                     else:
#                         yield fs.pop().result(end_time - time.monotonic())
#             finally:
#                 for future in fs:
#                     future.cancel()
#
#         return result_iterator()
#
#     def shutdown(self):
#         # super().close()
#         self._parent.close()
#         # super().join()
#         self._parent.join()
#         return
################################################################################


class amped_error(Exception):
    pass


class amped:
    """
    Class for creating and managing multiple processes and threads, with the ability to run them asynchronously.

    Attributes
    ----------
    For all operating systems:
        _affinity : list[int]
            A list of which CPU cores are usable by the program.
        _cores_logical : list[int]
            The number of logical CPU cores for each socket on the system.
        _cores_physical : list[int]
            The number of physical CPU cores for each socket on the system.
        _cores_usable: list[int]
            The CPU cores that are usable by this Python process, also known as the CPU affinity of the process.
            Each integer in the list is numbered after a single logical CPU core.
            The elements' values range from core 0 to the maximum number of logical CPU cores on the system.
        _cores_user : list[int]
            A list of integers representing the CPU cores to utilize as specified by the user.
            Each integer in the list is numbered after a single logical CPU core.
            The elements' values range from core 0 to the maximum number of logical CPU cores on the system.
        _log : logging.RootLogger, None
            RootLogger object for writing messages to a file.
            If not provided hen messages are printed to the console's stdout.
        _pid : int
            The process ID for the main Python process.
        _platform_cpu : str
            The CPU information as identified from the platform module.
        _platform_machine : str
            The system's CPY architecture information as identified from the platform module.
        _platform_node : str
            The system's unique name as identified from the platform module.
        _platform_release : str
            The OS release information as identified from the platform module.
        _platform_system : str
            The OS name as identified from the platform module.
        _platform_version : str
            The full OS version number as identified from the platform module.
        _python_version_major : str
            The major Python executable version number.
        _python_version_minor : str
            The minor Python executable version number.
        _python_version_patch : str
            The patch Python executable version number.
        _smt : list[bool]
            A list of bools defining whether SMT is enabled for each socket in the system.
        _sys_platform : str
            The system's OS name as identifed from the sys module.

    Only for Windows operating systems:
        _windows_version_build : str
            The Windows build version number.
        _windows_version_major : str
            The Windows major version number.
        _windows_version_minor : str
            The Windows minor version number.
    """

    def __init__(
        self,
        affinity: Union[Sequence[int], Set[int]] = (),
        log: Optional[lg.RootLogger] = None,
    ):
        """
        Contructs the amped object and collects system information.

        Parameters
        ----------
            affinity : list[int], tuple[int], None
                A list/set/tuple of integers which represents the CPU core affinity to use.
                If it's a list/set/tuple, it should contain integers specifiying which cores to utilize specifically.
                The range should from 0 to the max number of cores on the system.
                Values less than 0 or greater than the max core number are truncated, and duplicate entrieis are removed.
                If the value is None then the program will automatically use all the cores it can.

            log : logging.RootLogger, None
                A logging.RootLogger object to use for logging purposes.
                If None, then the logging messages will be printed to the console.
        """

        if log is not None and isinstance(log, lg.RootLogger):
            self._log = log
        else:
            self._log = None

        ret = plat.uname()
        self._platform_system = ret[0]
        self._platform_node = ret[1]
        self._platform_release = ret[2]
        self._platform_version = ret[3]
        self._platform_machine = ret[4]
        self._platform_cpu = ret[5]

        self._get_info()

        if sys.platform == "linux":
            self._sys_platform = "Linux"
        elif sys.platform == "aix":
            self._sys_platform = "AIX"
        elif sys.platform == "win32":
            self._sys_platform = "Windows"
        elif sys.platform == "darwin":
            self._sys_platform = "MacOS"
        elif sys.platform.startswith("freebsd"):
            self._sys_platform = "FreeBSD"

        _check_instance(
            affinity,
            "affinity",
            (
                list,
                set,
                tuple,
            ),
            can_be_none=False,
        )

        if not all(True if isinstance(i, int) else False for i in affinity):
            msg = "'affinity' argument is not a valid type - requires a list / set / tuple of integers."
            self._log_exception(TypeError(msg))

        affinity = sorted(list(set(affinity)))
        affinity = [i for i in affinity if i >= 0 and i <= (len(self._cores_usable) - 1)]

        if len(affinity) >= len(self._cores_usable) or len(affinity) <= 0:
            self._cores_user = self._cores_usable
        elif 0 < len(affinity) and len(affinity) <= len(self._cores_usable):
            self._cores_user = affinity
        else:
            self._cores_user = self._cores_usable

        psutil.Process().cpu_affinity(self._cores_user)

    def _log_exception(self, ex):
        if self._log is not None:
            self._log.error(ex)
        raise type(ex)(ex)

    def _get_info(self):
        self._pid = os.getpid()
        # psutil process object for main process
        self._process = psutil.Process(self._pid)
        # Get main process data
        with self._process.oneshot():
            self._name = self._process.name()
            self._pid = self._process.pid
            self._nice = self._process.nice()
            self._ionice = self._process.ionice()
            self._affinity = self._process.cpu_affinity()
            self._threads = self._process.threads()
            self._num_threads = self._process.num_threads()
            self._children = self._process.children()
            self._parent = self._process.parent()
            self._ppid = self._process.ppid()

        self._cores_physical = psutil.cpu_count(logical=False)
        self._cores_logical = psutil.cpu_count()
        self._smt = True if self._cores_logical > self._cores_physical else False

        # For saving count of CPU sockets in systems, mostly for multi-socket use
        self._sockets = 0
        # Which cores are usable, based on the affinity for this process
        self._cores_usable = tuple(self._affinity)
        # List of cores that are in use by this program - can only use cores as specified by the user
        self._cores_used = []
        # Dictionary containing pools and their associated data
        self._pools = {}

    # def _get_info_freebsd(self) -> None:
    #     """
    #     Get system information for FreeBSD systems.
    #
    #         Parameters:
    #             None
    #     """
    #     int(os.popen("sysctl -n hw.ncpu").readlines()[0])

    def _time_function(self, func: Callable, sema: sync.Semaphore, rlock: sync.RLock, *args: Any, **kwargs: Any) -> Mapping:
        ret = {}
        ret["Success"] = False
        ret["return"] = None
        was_acquired = False
        try:
            was_acquired = True
            sema.acquire()
            ret["return"] = func(*args, **kwargs, sema=sema)
            sema.release()
            was_acquired = False
            ret["Success"] = True
            return ret
        except Exception as e:
            if was_acquired:
                sema.release()
            ret["Success"] = False
            self._log_exception(e)

    def get_affinity(self) -> Iterable:
        return self._cores_usable

    def set_affinity(self, affinity: Union[Sequence[int], Set[int]]) -> bool:
        # Remove duplicate entries
        new_affinity = set(affinity)

        # Make sure there are elements
        if len(new_affinity) == 0:
            self._log_exception(ValueError("No affinity was provided."))

        # Get rid of any elements greater than the highest core number
        while max(new_affinity) > max(self._cores_usable):
            new_affinity.discard(max(new_affinity))

        # Make sure there are no entries less than 0
        while min(new_affinity) < min(self._cores_usable):
            new_affinity.discard(min(new_affinity))

        # Make sure we still have elements after removing the above values
        if len(new_affinity) == 0:
            msg = "No affinity values remain after removing unusable values."
            self._log_exception(ValueError(msg))

        self._cores_usable = tuple(new_affinity)
        return True

    def _pool_check(self, group: str, name: str):
        if group not in self._pools.keys():
            msg = "Group '{}' does not exist in the list of pools."
            self._log_exception(KeyError(msg.format(group)))

        if name not in self._pools[group].keys():
            msg = "Pool by the name of '{}' does not exist in the group '{}'."
            self._log_exception(KeyError(msg.format(name, group)))

    def create(
        self,
        library: Literal["concurrent", "multiprocessing"] = "concurrent",
        pool_type: Literal["process", "thread"] = "thread",
        group: str = "",
        name: str = "",
        affinity: Union[Sequence[int], Set[int], MutableSet[int]] = (),
        affinity_type: Literal["queue", "list"] = "queue",
        choice: bool = False,
        initializer: Optional[Callable[..., None]] = None,
        initargs: Tuple[Any, ...] = (),
    ) -> Union[
        # _amped_process_pool_cf, _amped_thread_pool_cf, _amped_process_pool_mp, None
        _amped_process_pool_cf,
        _amped_thread_pool_cf,
        None,
    ]:
        """
        Create a pool of threads or processes.
        """
        # Make sure the 'library' argument is a string
        # _check_instance(library, "library", str, can_be_none=False)
        # Make sure the 'pool_type' argument is a string
        # _check_instance(pool_type, "pool_type", str, can_be_none=False)

        # Defines what class to use based on given call to this function
        pool_class = None

        # 'concurrent' library supports both process and thread pools
        if library == "concurrent":
            if pool_type == "process":
                pool_class = _amped_process_pool_cf
            elif pool_type == "thread":
                pool_class = _amped_thread_pool_cf
            else:
                msg = "'pool_type' has an incorrect value - it should either be 'process' or 'thread'."
                self._log_exception(ValueError(msg))

        # Make sure the `group` argument is a string
        _check_instance(group, "group", str, can_be_none=False)

        # If no group name is given, then assign it the default group name of `main`
        if group == "":
            group = "main"
            print("No group name was given - using default group name 'main'.")

        # Make sure the 'affinity' argument is some sort of iterable
        _check_instance(
            affinity,
            "affinity",
            (
                list,
                set,
                tuple,
            ),
            can_be_none=False,
        )

        # If the length of `affinity` is 0 ir greater than the number of cores/threads
        # on the system, then assume to use all cores/threads
        if len(affinity) == 0 or len(affinity) >= len(self._cores_user):
            affinity = list(self._cores_user)
        # Otherwise if the length of 'affinity' is less than the number of
        # cores/threads on the system, use the provided affinity and convert it
        # into a list
        elif len(affinity) <= len(self._cores_user):
            affinity = list(affinity)

        # Make sure that the parent process is assigned the cores that are being
        # assigned to the pool.
        # This is to prevent users from creating pools with access to cores/threads
        # that the parent does not have access to.
        if not set(affinity).issubset(set(self._cores_user)):
            msg = "The specified affinity '{}' is not available for use when the parent affinity is '{}'."
            self._log_exception(ValueError(msg.format(affinity, self._cores_user)))

        # Make sure the 'name' argument is a string.
        _check_instance(name, "name", str, can_be_none=False)
        # If no name is given then assign it the name of the group, library, and
        # pool_type combined.
        if name == "":
            name = "{}-{}-{}".format(group, library, pool_type)

        # If the group name is not already in the list of pools, then add it to
        # the list of pools, otherwise continue.
        if group not in self._pools.keys():
            self._pools[group] = {}

        # If the name of the new pool already exists within the given group,
        # then raise an exception.
        if name in self._pools[group].keys():
            msg = "Pool name '{}' already exists - please choose a different pool name, or run the 'pool_update' function with the relevant arguments."
            self._log_exception(KeyError(msg.format(name)))

        # Create the pool with a given name under the given group with the
        # related data filled in.
        self._pools[group][name] = {}
        self._pools[group][name]["parent"] = psutil.Process().parent()
        self._pools[group][name]["affinity"] = tuple(affinity)
        self._pools[group][name]["affinity_type"] = affinity_type
        self._pools[group][name]["choice"] = choice
        self._pools[group][name]["initializer"] = initializer
        self._pools[group][name]["initargs"] = tuple(initargs)

        # Attempt to create the pool with the given variables
        # Otherwise raise an error
        try:
            self._pools[group][name]["pool"] = pool_class(
                name=name,
                affinity=self._pools[group][name]["affinity"],
                affinity_type=self._pools[group][name]["affinity_type"],
                choice=self._pools[group][name]["choice"],
                # mp_context=self._mp_ctx,
                initializer=self._pools[group][name]["initializer"],
                initargs=self._pools[group][name]["initargs"],
            )
            return self._pools[group][name]["pool"]
        except Exception as e:
            self._log_exception(e)
            return

    def shutdown(self, group: str, name: str, wait=True, cancel_futures=False):
        self._pool_check(group, name)

        ret = self._pools[group][name]["pool"].shutdown(wait=wait, cancel_futures=cancel_futures)
        del self._pools[group][name]
        return ret

    def submit(self, group: str, name: str, function: Callable, *args: Any, **kwargs: Any):
        self._pool_check(group, name)

        return self._pools[group][name]["pool"].submit(function, *args, **kwargs)

    def map(self, group: str, name: str, map_type: Literal["normal", "wrapper", "builtin"], function: Callable, *args: Any, chunksize: int = 1):
        self._pool_check(group, name)

        return self._pools[group][name]["pool"].map(function, chunksize=chunksize, *args)

    def map_wrapper(self, group: str, name: str, function: Callable, *args: Any, chunksize: int = 1):
        self._pool_check(group, name)

        return self._pools[group][name]["pool"].map_wrapper(function, chunksize=chunksize, *args)

    def map_builtin(self, group: str, name: str, function: Callable, *args: Any, chunksize: int = 1):
        self._pool_check(group, name)

        return self._pools[group][name]["pool"].map_builtin(function, chunksize=chunksize, *args)
