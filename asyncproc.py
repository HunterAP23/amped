# Process related
import asyncio
import psutil
import multiprocessing as mp
import multiprocessing.pool
import multiprocessing.synchronize as sync
import subprocess as sp

# Scheduling related
import sched
import functools as ft

# System related
import os
import platform as plat
import shlex
import sys

# Debugging related
import errno
import inspect
import logging as lg
import traceback

# Typing
from typing import Any, Callable, Iterable, Mapping, Type, Union

# Miscellaneous
import re


def _check_instance(var: Any, name: str, types: Union[Type, tuple[Type, ...]], can_be_none=True) -> None:
    if not isinstance(var, types) and var is None and not can_be_none:
        raise TypeError("\"{}\" object is not of type {}.".format(name, types))


def _check_callable(func: Callable, name: str, can_be_none=True) -> None:
    if not callable(func) and func is not None:
        raise TypeError("Function \"{}\" object is not callable.".format(name))


class asyncproc_error(Exception):
    pass


class asyncproc:
    """
    Class for creating and managing multiple processes and threads, with the ability to run them asynchronously.

    Attributes
    ----------
    For all operating systems:
        _cores_count : int
            The number of logical CPU cores the system has available in total.
        _cores_logical : list[int]
            The number of logical CPU cores for each socket on the system.
        _cores_physical : list[int]
            The number of physical CPU cores for each socket on the system.
        _cores_usable: list[int]
            The CPU cores that are usable by this Python process, also known as the CPU affinity of the process.
            Each integer in the list is numbered after a single logical CPU core.
            The elements' values range from core 0 to the maximum number of logical CPU cores on the system.
        _cores_usable_count : int
            A count of logical CPU cores available to this Python process.
        _cores_user : list[int]
            A list of integers representing the CPU cores to utilize as specified by the user.
            Each integer in the list is numbered after a single logical CPU core.
            The elements' values range from core 0 to the maximum number of logical CPU cores on the system.
        _cores_user_count : int
            A count of CPU cores to utilize as specified by the user.
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
        _sockets_count : int
            A count of the number of sockets in the system.
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

    def __init__(self, affinity: Union[list, set, tuple] = (), log: Union[lg.RootLogger, None] = None):
        """
        Contructs the asyncproc object and collects system information.

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

        ret = plat.python_version_tuple()
        self._python_version_major = ret[0]
        self._python_version_minor = ret[1]
        self._python_version_patch = ret[2]

        del ret
        self._get_info()

        if sys.platform == "linux":
            self._sys_platform = "Linux"
            self._get_info_linux()
        elif sys.platform == "aix":
            self._sys_platform = "AIX"
        elif sys.platform == "win32":
            self._sys_platform = "Windows"
            try:
                global win32api
                import win32api
                global win32com
                import win32com
                import win32com.client
                global win32con
                import win32con
                global win32process
                import win32process
            except ModuleNotFoundError as mnfe:
                if self._log is not None:
                    self._log.error(mnfe)
                print(mnfe)
                exit(1)
            self._get_info_windows()
        elif sys.platform == "darwin":
            self._sys_platform = "MacOS"
            self._get_info_macos()
        elif sys.platform.startswith("freebsd"):
            self._sys_platform = "FreeBSD"

        _check_instance(affinity, "affinity", (list, set, tuple,), can_be_none=False)
        try:
            if not all(True if isinstance(i, int) else False for i in affinity):
                raise TypeError()

            affinity = sorted(list(set(affinity)))
            if len(affinity) >= len(self._cores_usable) or len(affinity) <= 0:
                self._cores_user = self._cores_usable
            elif 0 < len(affinity) and len(affinity) <= len(self._cores_usable):
                self._cores_user = affinity
            else:
                self._cores_user = self._cores_usable
        except TypeError as te:
            raise TypeError("\"affinity\" argument is not a valid type - requires a list / set / tuple of integers.")

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
        self._smt = (True if self._cores_logical > self._cores_physical else False)

        # For saving count of CPU sockets in systems, mostly for multi-socket use
        self._sockets = 0
        # Which cores are usable, based on the affinity for this process
        self._cores_usable = self._affinity
        # List of cores that are in use by this program - can only use cores as specified by the user
        self._cores_used = []
        # Dictionary containing pools and their associated data
        self._pools = {}
        # # Set the multiprocessing conext for the program to "spawn" by default.
        # # "spawn" is slower but safer than forking, and is usable on all operating systems.
        # mp.set_start_method("spawn")
        # self._mp_ctx = mp.get_context("spawn")

    def _get_info_freebsd(self) -> None:
        """
        Get system information for FreeBSD systems.

            Parameters:
                None
        """
        int(os.popen("sysctl -n hw.ncpu").readlines()[0])

    def _get_info_linux(self) -> None:
        """
        Get system information for Linux systems.

        Parameters
        ----------

        """
        if sys.platform != "linux":
            if self._log is not None:
                self._log.error("Operating system is not Linux.")
            raise OSError("Operating system is not Linux.")

        dict_lscpu = {}
        check = [
            "CPU(s)",
            "On-line CPU(s) list",
            "Thread(s) per core",
            "Core(s) per socket",
            "Socket(s)"
        ]

        cmd = shlex.split("lscpu")
        ret = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE)
        out, err = ret.communicate()
        for line in out.decode().strip().split("\n"):
            items = line.split(":")
            key = items[0].strip()
            value = items[1].strip()
            if key in check:
                dict_lscpu[key] = value

        self._sockets = int(dict_lscpu["Socket(s)"])
        self._cores_physical = int(dict_lscpu["Core(s) per socket"])
        self._cores_logical = int(dict_lscpu["CPU(s)"])
        tmp_range = str(dict_lscpu["On-line CPU(s) list"]).split("-")
        self._cores_usable = tuple(i for i in range(int(tmp_range[0]), int(tmp_range[1]) + 1))
        self._smt = int(dict_lscpu["Thread(s) per core"]) > 1

    # INCOMPLETE - NEEDS TESTING ON MAC OS
    def _get_info_macos(self) -> None:
        if sys.platform != "darwin":
            if self._log is not None:
                self._log.error("Operating system is not MacOS.")
            raise OSError("Operating system is not MacOS.")

        tmp_dict = {}
        check = [
            "ncpu",
            "activecpu",
            "physicalcpu",
            "physicalcpu_max",
            "logicalcpu",
            "logicalcpu_max"
        ]
        cmd = shlex.split("sysctl hw")
        ret = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE)
        out, err = ret.communicate()
        for line in out.decode():
            for item in line.split(":"):
                key = item[0].replace(" ", "").replace("\"", "").strip("hw.").lower()
                value = item[1].strip(".\n ")
                if key in check:
                    tmp_dict[key] = value

    def _get_info_windows(self) -> None:
        if sys.platform != "win32":
            if self._log is not None:
                self._log.error("Operating system is not Windows.")
            raise OSError("Operating system is not Windows.")

        tmp = sys.getwindowsversion()
        self._windows_version_major = tmp.major
        self._windows_version_minor = tmp.minor
        self._windows_version_build = tmp.build

        # Get simultaneous multithreading info
        # https://docs.microsoft.com/en-us/windows/win32/cimwin32prov/win32-processor
        winmgmts_root = win32com.client.GetObject("winmgmts:root\\cimv2")
        cpus = winmgmts_root.ExecQuery("Select * from Win32_Processor")
        for cpu in cpus:
            self._sockets += 1
            # self._cores_physical += cpu.NumberOfCores
            # self._cores_logical += cpu.NumberOfLogicalProcessors
            # if cpu.NumberOfCores < cpu.NumberOfLogicalProcessors:
            #     self._smt = True

        # Get affinity info
        handle = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, True, self._pid)
        mask = win32process.GetProcessAffinityMask(handle)

        self._cores_usable = self._mask_to_affinity(self._int_to_mask(int(mask[0])))

    def _int_to_mask(self, int_val: int) -> tuple[int, ...]:
        if not isinstance(int_val, int):
            raise TypeError("\"int_val\" argument was not an int or str.")
        ret = "{0:08b}".format(int(int_val))
        ret2: tuple[int, ...] = tuple(int(i) for i in ret)
        return ret2

    def _mask_to_int(self, mask: tuple[int, ...]) -> tuple[int, ...]:
        ret = "".join(str(mask))
        ret2: tuple[int, ...] = tuple(int(i) for i in ret)
        return ret2

    def _mask_to_affinity(self, mask: tuple[int, ...]) -> tuple[int, ...]:
        mask_reversed = list(reversed(list(mask)))
        ret: tuple[int, ...] = tuple(int(i) for i in range(len(mask_reversed)) if int(mask_reversed[i]) == 1)
        return ret

    def _affinity_to_mask(self, affinity: tuple[int, ...]) -> tuple[int, ...]:
        affinity_list = list(affinity)
        mask_list = []
        start = 0
        while True:
            if len(affinity_list) == 0:
                break
            min_val = int(min(affinity_list))
            if len(mask_list) > 0 and len(mask_list) == min_val:
                pass
            else:
                for i in range(start, min_val):
                    mask_list.append(0)
            mask_list.append(1)
            start = min_val
            affinity_list.remove(min_val)

        while len(mask_list) % 8 != 0:
            mask_list.append(0)

        mask_reversed = list(reversed(mask_list))
        ret: tuple[int, ...] = tuple(mask_reversed)
        return ret

    # def _run_in_parallel(self, functions: Union[dict, list, tuple], arguments: Union[dict, list, tuple], threads: int, sema: mp.synchronize.Semaphore, rlock: mp.synchronize.RLock):
    #     # proc = []
    #     # for func in funcs:
    #     #     p = mp.Process(target=self._time_function, args=(func, args[func], sema, rlock))
    #     #     proc.append(p)
    #     #
    #     # for p in proc:
    #     #     p.start()
    #     #
    #     # for p in proc:
    #     #     try:
    #     #         p.join()
    #     #     except Exception as e:
    #     #         self._log.error(e)
    #     funcs_data = {}
    #     args_data = {}
    #     try:
    #         # Handle functions
    #         funcs_items = []
    #         if len(functions) == 0:
    #             raise IndexError("No functions were given.")
    #         elif isinstance(functions, dict):
    #             funcs_items = [(name, func) for name, func in functions.items()]
    #         elif isinstance(functions, (list, tuple)):
    #             for item in functions:
    #                 # Expect pair of "name, function" as a dict, list, or tuple
    #                 if not isinstance(item, (dict, tuple, list)):
    #                     raise TypeError("Function list contains a non-iterable element (requires a dict, list, or tuple).")
    #             funcs_items = [(name, func) for name, func in functions]
    #         for name, func in funcs_items:
    #             if self._test_callable(name, func):
    #                 funcs_data[name] = {}
    #                 funcs_data[name]["Function"] = func
    #         if len(funcs_data) == 0:
    #             raise IndexError("None of the given functions are callable.")
    #
    #         # Handle arguments
    #         args_items = []
    #         if not self._no_args and len(arguments) == 0:
    #             raise IndexError("User specified that arguments are required but did no arguments were given.")
    #         elif isinstance(arguments, dict):
    #             args_items = [(name, value) for name, value in arguments.items()]
    #         elif isinstance(arguments, (list, tuple)):
    #             for item in arguments:
    #                 # Expect pair of "name, function" as a dict, list, or tuple
    #                 if not isinstance(item), (dict, tuple, list)):
    #                     raise TypeError("Argument list contains a non-iterable element (requires a dict, list, or tuple).")
    #                 elif isinstance(item, dict):
    #                     args_items = [(name, value) for name, value in item]
    #                 elif isinstance(item, (list, tuple)):
    #                     args_items = [(name, value) for name, value in item]
    #         for name, func in args_items:
    #             if self._test_callable(name, func):
    #                 args_data[name] = {}
    #                 args_data[name]["Function"] = func
    #         if len(funcs_data) == 0:
    #             raise IndexError("None of the given functions are callable.")
    #     except IndexError as ie:
    #         if self._log is not None:
    #             self._log.error(ie)
    #         exit(1)
    #
    #     self._run_map(func)

    def _run_map(self, func, args, name: str):
        return

    def _time_function(self, func: Callable, sema: sync.Semaphore, rlock: sync.RLock, *args: Union[list, set, tuple, None], **kwargs: Union[dict, None]) -> dict:
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
            if self._log is not None:
                self._log.error(e)
            raise TypeError(e)

    def get_affinity(self) -> tuple:
        return self._cores_usable

    def set_affinity(self, affinity: Union["list[int]", "set[int]", "tuple[int]"]) -> bool:
        # Remove duplicate entries
        new_affinity = set(affinity)

        # Make sure there are elements
        if len(new_affinity) == 0:
            raise ValueError("No affinity was provided.")

        # Get rid of any elements greater than the highest core number
        while max(new_affinity) > max(self._cores_usable):
            new_affinity.discard(max(new_affinity))

        # Make sure there are no entries less than 0
        while min(new_affinity) < min(self._cores_usable):
            new_affinity.discard(min(new_affinity))

        # Make sure we still have elements after removing the above values
        if len(new_affinity) == 0:
            raise ValueError("No affinity values remain after removing unusable values.")

        self._cores_usable = tuple(new_affinity)
        return True

    # def get_thread_count(self):
    #     return thrd.active_count()

    def create_pool(self, pool_type: str = "", group: str = "", name: str = "", affinity: Union[list, set, tuple] = tuple(), initializer: Union[Callable, None] = None, initargs: Union[list, set, tuple] = ()):
        _check_instance(pool_type, "pool_type", str, can_be_none=False)
        pool_class = None
        if pool_type == "process" or pool_type == "":
            pool_class = asyncproc_process_pool
        elif pool_type == "thread":
            pool_class = asyncproc_thread_pool
        else:
            raise ValueError("\"pool_type\" has an incorrect value - it should either be \"process\" or \"thread\".")

        _check_instance(group, "group", str, can_be_none=False)
        if group == "":
            group = "main"

        _check_instance(affinity, "affinity", (list, set, tuple,), can_be_none=False)
        if len(affinity) == 0:
            affinity = list(self._cores_user)
        elif 0 < len(affinity) and len(affinity) <= len(self._cores_usable):
            affinity = list(affinity)

        _check_instance(name, "name", str, can_be_none=False)
        if name == "":
            name = "{}-{}".format(group, pool_type)

        # _check_callable(initializer, "initializer")
        # print(initializer)
        # if not callable(initializer) and initializer is not None:
        #     raise TypeError("Function \"initializer\" object is not callable.")

        if group not in self._pools.keys():
            self._pools[group] = {}
        if name in self._pools[group].keys():
            msg = "Pool name \"{}\" already exists - please choose a different pool name, or run the \"pool_update\" function with the relevant arguments."
            raise KeyError(msg.format(name))
        self._pools[group][name] = {}
        self._pools[group][name]["parent"] = psutil.Process().parent()
        self._pools[group][name]["affinity"] = tuple(affinity)
        self._pools[group][name]["initializer"] = initializer
        self._pools[group][name]["initargs"] = tuple(initargs)

        try:
            self._pools[group][name]["pool"] = pool_class(
                name=name,
                affinity=self._pools[group][name]["affinity"],
                # mp_context=self._mp_ctx,
                initializer=self._pools[group][name]["initializer"],
                initargs=self._pools[group][name]["initargs"]
            )
        except Exception as e:
            if self._log is not None:
                self._log.error(e)
            raise type(e)(e)

    def run_pool(self, function: Union[Callable, None] = None, *args: Any, **kwargs: Union[Mapping, None]):
        return


class asyncproc_process_pool(multiprocessing.pool.Pool):
    def __init__(self, name: str, affinity: list[int], initializer: Union[Callable, None] = None, initargs: tuple = (), maxtasksperchild: Union[int, None] = None, context: Union[mp.context.SpawnContext, None] = None):
        self._name = name
        self._affinity = affinity
        self._processes = len(affinity)
        self._initializer = initializer
        self._initargs = initargs
        self._maxtasksperchild = maxtasksperchild
        self._context = context

        if initializer is None:
            super().__init__(processes=self._processes, maxtasksperchild=maxtasksperchild, context=context)
        elif initializer is not None and len(initargs) != 0:
            super().__init__(processes=self._processes, initializer=self._initializer, maxtasksperchild=self._maxtasksperchild, context=self._context)
        else:
            super().__init__(processes=self._processes, initializer=self._initializer, initargs=self._initargs, maxtasksperchild=self._maxtasksperchild, context=self._context)

    def submit(self, func: Callable, *args: Any, **kwargs: Union[Mapping, None]):
        return


@announce_name
class asyncproc_thread_pool(multiprocessing.pool.ThreadPool):
    def __init__(self, name: str, affinity: list[int], initializer: Union[Callable, None] = None, initargs: tuple = (), maxtasksperchild: Union[int, None] = None, context: Union[mp.context.SpawnContext, None] = None):
        self._name = name
        self._affinity = affinity
        self._processes = len(affinity)
        self._initializer = initializer
        self._initargs = initargs

        if initializer is None:
            super().__init__(processes=self._processes)
        # elif initializer is not None and len(initargs) != 0:
        #     super().__init__(processes=self._processes, initializer=self._initializer)
        else:
            super().__init__(processes=self._processes, initializer=self._initializer, initargs=self._initargs)
