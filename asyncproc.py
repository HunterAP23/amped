# Process related
import asyncio
import multiprocessing as mp
import multiprocessing.synchronize
import multiprocessing.dummy as mpd
import subprocess as sp
import threading as thrd

# Scheduling related
import sched

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
from typing import Any, Callable, Tuple, Type, Union

# Miscellaneous
import re


class asyncproc_argument:
    def __init__(self, name: str, value: Any, arg_type: type, function_name: str):
        self.name = name
        self.value = value,
        self.type = arg_type
        self.function = function_name

    def get(self) -> dict:
        return vars(self)


class asyncproc_process(mp.Process):
    def __init__(self, group: Union[str, None] = None, target: Union[Callable, None] = None, name: Union[str, None] = None, args=(), kwargs={}, *, daemon: Union[bool, None] = None):
        if type(group) != str and group is not None:
            raise TypeError("\"group\" object is not a string.")
        if not callable(target) and target is not None:
            raise TypeError("\"target\" object is not callable")
        if type(args) not in (list, set, tuple) and args is not None:
            raise TypeError("\"args\" argument is not a list, set or tuple.")
        if type(kwargs) != dict and kwargs is not None:
            raise TypeError("\"kwargs\" argument is not a dictionary.")
        if type(daemon) != bool and daemon is not None:
            raise TypeError("\"daemon\" argument is not a bool")
        super().__init__(target=target, name=name, args=args, kwargs=kwargs, daemon=daemon)
        self._group = group


class asyncproc_thread(thrd.Thread):
    def __init__(self, group: Union[str, None] = None, target: Union[Callable, None] = None, name: Union[str, None] = None, args=(), kwargs={}, *, daemon: Union[bool, None] = None):
        if type(group) != str and group is not None:
            raise TypeError("\"group\" object is not a string.")
        if not callable(target) and target is not None:
            raise TypeError("\"target\" object is not callable")
        if type(args) not in (list, set, tuple) and args is not None:
            raise TypeError("\"args\" argument is not a list, set or tuple.")
        if type(kwargs) != dict and kwargs is not None:
            raise TypeError("\"kwargs\" argument is not a dictionary.")
        if type(daemon) != bool and daemon is not None:
            raise TypeError("\"daemon\" argument is not a bool")
        super().__init__(target=target, name=name, args=args, kwargs=kwargs, daemon=daemon)
        self._group = group


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

    def __init__(self, cores: Union[list[int], set[int], tuple[int], None] = None, log: Union[lg.RootLogger, None] = None):
        """
        Contructs the asyncproc object and collects system information.

        Parameters
        ----------
            cores : list[int], tuple[int], None
                A list/set/tuple of integers which represents the CPU core affinity to use.
                If it's a list/set/tuple, it should contain integers specifiying which cores to utilize specifically.
                The range should from 0 to the max number of cores on the system.
                Values less than 0 or greater than the max core number are truncated, and duplicate entrieis are removed.
                If the value is None then the program will automatically use all the cores it can.

            log : logging.RootLogger, None
                A logging.RootLogger object to use for logging purposes.
                If None, then the logging messages will be printed to the console.
        """

        if type(cores) not in (list, set, tuple) and cores is not None:
            raise TypeError("\"cores\" argument is not a valid type - requires list[int], set[int], tuple[int], None]")
        else:
            if type(cores) in (list, set, tuple):
                if not all(True if type(i) == int else False for i in cores):
                    raise TypeError("\"cores\" argument is not a valid type - requires list[int], set[int], tuple[int], None]")
            elif cores is not None:
                raise TypeError("\"cores\" argument is not a valid type - requires list[int], set[int], tuple[int], None]")

        if log is not None and type(log) is not lg.RootLogger:
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

        self._thread_count = self.get_thread_count()

        del ret

        # Save this Python process' PID for future use.
        self._pid = os.getpid()
        # Get the reported number of CPU cores
        self._cores_count = mp.cpu_count()
        # For saving count of CPU sockets in systems, mostly for multi-socket use
        self._sockets_count = 0
        # Which cores are usable, based on the affinity for this process
        self._cores_usable = ()
        # Number of usable cores
        self._cores_usable_count = 0
        # List of physical cores - typically even numbered starting at 0
        self._cores_physical = []
        # List of logical cores - typically odd numbered starting at 1
        self._cores_logical = []
        # Whether the system has Simultaneous Multithreading / Hyperthreading
        # This is a list for measuring SMT on multiple sockets,
        self._smt = []
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
                print(mnfe)
                exit(1)
            self._get_info_windows()
        elif sys.platform == "darwin":
            self._sys_platform = "MacOS"
            self._get_info_macos()
        elif sys.platform.startswith("freebsd"):
            self._sys_platform = "FreeBSD"

        self._cores_user = None
        self._cores_user_count = None
        if  cores is None or len(cores) >= self._cores_usable_count:
            self._cores_user = self._cores_usable
            self._cores_user_count = self._cores_usable_count
        elif 0 < len(cores) and len(cores) <= self._cores_usable_count:
            self._cores_user = cores
            self._cores_user_count = len(self._cores_user)
        else:
            self._cores_user = self._cores_usable
            self._cores_user_count = self._cores_usable_count

        # A dictionary of processes, with keys being the group name.
        self._processes = {}
        # A dictionary of threads, with keys being the group name.
        self._threads = {}

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
            raise OSError("Operating system is not Linux.")

        self._cores_usable = tuple(os.sched_getaffinity(0))
        self._cores_usable_count = len(self._cores_usable)

        dict_lscpu = {}
        check = [
            "CPU(s)",
            "On-line CPU(s) list",
            "Thread(s) per core",
            "Core(s) per socket",
            "Socket(s)",
            "Model name"
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

        self._sockets_count = int(dict_lscpu["Socket(s)"])
        self._cores_physical = int(dict_lscpu["Core(s) per socket"])
        self._cores_logical = int(dict_lscpu["CPU(s)"])
        tmp_range = str(dict_lscpu["On-line CPU(s) list"]).split("-")
        self._cores_usable = tuple(i for i in range(int(tmp_range[0]), int(tmp_range[1]) + 1))
        self._smt = int(dict_lscpu["Thread(s) per core"]) > 1
        self._model_name = dict_lscpu["Model name"]

    # INCOMPLETE - NEEDS TESTING ON MAC OS
    def _get_info_macos(self) -> None:
        if sys.platform != "darwin":
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
        for line in out:
            for item in line.split(":"):
                key = item[0].replace(" ", "").replace("\"", "").strip("hw.").lower()
                value = item[1].strip(".\n ")
                if key in check:
                    tmp_dict[key] = value

    def _get_info_windows(self) -> None:
        if sys.platform != "win32":
            raise OSError("Operating system is not Windows.")

        tmp = sys.getwindowsversion()
        self._windows_version_major = tmp.major
        self._windows_version_minor = tmp.minor
        self._windows_version_build = tmp.build

        self._cores_physical = 0
        self._cores_logical = 0

        # Get simultaneous multithreading info
        # https://docs.microsoft.com/en-us/windows/win32/cimwin32prov/win32-processor
        winmgmts_root = win32com.client.GetObject("winmgmts:root\\cimv2")
        cpus = winmgmts_root.ExecQuery("Select * from Win32_Processor")
        for cpu in cpus:
            self._sockets_count += 1
            self._cores_physical += cpu.NumberOfCores
            self._cores_logical += cpu.NumberOfLogicalProcessors
            if cpu.NumberOfCores < cpu.NumberOfLogicalProcessors:
                self._smt = True
            self._model_name = cpu.Name

        # Get affinity info
        handle = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, True, self._pid)
        mask = win32process.GetProcessAffinityMask(handle)

        self._cores_usable = self._mask_to_affinity(self._int_to_mask(int(mask[0])))
        self._cores_usable_count = len(self._cores_usable)

    def _int_to_mask(self, int_val: int) -> Tuple[str, ...]:
        if type(int_val) != int:
            raise TypeError("\"int_val\" argument was not an int or str.")
        ret = "{0:08b}".format(int(int_val))
        ret2: Tuple[str, ...] = tuple(i for i in ret)
        return ret2

    def _mask_to_int(self, mask: Tuple[str, ...]) -> Tuple[str, ...]:
        ret = "".join(mask)
        ret2: Tuple[str, ...] = tuple(i for i in ret)
        return ret2

    def _mask_to_affinity(self, mask: Tuple[str, ...]) -> Tuple[str, ...]:
        mask_reversed = list(reversed(list(mask)))
        ret: Tuple[str, ...] = tuple(str(i) for i in range(len(mask_reversed)) if int(mask_reversed[i]) == 1)
        return ret

    def affinity_to_mask(self, affinity: Tuple[str, ...]) -> Tuple[str, ...]:
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
            affinity_list.remove(str(min_val))

        while len(mask_list) % 8 != 0:
            mask_list.append(0)

        mask_reversed = list(reversed(mask_list))
        ret: Tuple[str, ...] = tuple(mask_reversed)
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
    #         elif type(functions) is dict:
    #             funcs_items = [(name, func) for name, func in functions.items()]
    #         elif type(functions) in (list, tuple):
    #             for item in functions:
    #                 # Expect pair of "name, function" as a dict, list, or tuple
    #                 if type(item) not in (dict, tuple, list):
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
    #         elif type(arguments) is dict:
    #             args_items = [(name, value) for name, value in arguments.items()]
    #         elif type(arguments) in (list, tuple):
    #             for item in arguments:
    #                 # Expect pair of "name, function" as a dict, list, or tuple
    #                 if type(item) not in (dict, tuple, list):
    #                     raise TypeError("Argument list contains a non-iterable element (requires a dict, list, or tuple).")
    #                 elif type(item) is dict:
    #                     args_items = [(name, value) for name, value in item]
    #                 elif type(item) in (list, tuple):
    #                     args_items = [(name, value) for name, value in item]
    #         for name, func in args_items:
    #             if self._test_callable(name, func):
    #                 args_data[name] = {}
    #                 args_data[name]["Function"] = func
    #         if len(funcs_data) == 0:
    #             raise IndexError("None of the given functions are callable.")
    #     except IndexError as ie:
    #         if self._log is not None:
    #             self._log.critical(ie)
    #         else:
    #             print(ie)
    #         exit(1)
    #
    #     self._run_map(func)

    def _run_map(self, func, args, name: str):
        return

    def _test_callable(self, method: Callable, name: str) -> bool:
        try:
            if callable(method):
                return True
            else:
                msg = "{} is not a callable method and will be removed from the pool."
                if name is None:
                    raise TypeError(msg.format(name))
                else:
                    raise TypeError(msg.format(name))
        except TypeError as te:
            if self._log is not None:
                self._log.error(te)
            else:
                print(te)
            return False

    # def _time_function(self, func: Callable, args: Union[dict, list, set, tuple], sema: mp.synchronize.Semaphore, rlock: mp.synchronize.RLock) -> dict:
    #     ret = {}
    #     ret["Success"] = False
    #     was_acquired = False
    #     try:
    #         was_acquired = True
    #         sema.acquire()
    #         ret["return"] = func(**args, sema=sema)
    #         sema.release()
    #         was_acquired = False
    #         ret["Success"] = True
    #         return ret
    #     except Exception as e:
    #         if was_acquired:
    #             sema.release()
    #         ret["Success"] = False
    #         if self._log is not None:
    #             self._log.error(e)
    #         else:
    #             print(e)
    #         return ret

    def get_affinity(self) -> tuple:
        return self._cores_usable

    def set_affinity(self, affinity: Union[list[int], set[int], tuple[int]]) -> bool:
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

    def get_thread_count(self):
        return thrd.active_count()

    def create_process_pool(self, group: Union[str, None] = None, processes: Union[int, None] = None, function: Union[Callable, None] = None, args: Union[dict, list, set, tuple, None] = None) -> bool:
        check = (processes is None, (type(processes == int) and processes == 0))

        try:
            if group is not None:
                try:
                    group = str(group)
                except TypeError as te:
                    if self._log is not None:
                        self._log.error(te)
                    else:
                        print(te)
                    return False

                if group not in self._processes:
                    self._processes[group] = mp.Pool(self._cores_user_count)
                else:
                    ends_in_number = re.search(r"\d+$", group)
                    if ends_in_number is not None:
                        group_new = str(group.rstrip(ends_in_number.group()))
                        new_number = str(int(ends_in_number.group()) + 1)
                        self._processes[group_new + new_number] = mp.Pool(self._cores_user_count)
                    else:
                        self._processes[group + "-1"] = mp.Pool(self._cores_user_count)
                return True
            return False

        except Exception as e:
            if self._log is not None:
                self._log.error(e)
            else:
                print(e)
            return False

    def create_process(self, group: Union[str, None] = None, target: Union[Callable, None] = None, name: Union[str, None] = None, args=(), kwargs={}, daemon: Union[bool, None] = None):
        return

    def create_thread_pool(self, group: Union[str, None] = None, threads: Union[int, None] = None, function: Union[Callable, None] = None, args: Union[dict, list, set, tuple, None] = None):
        return

    def create_thread(self, group: Union[str, None] = None, target: Union[Callable, None] = None, name: Union[str, None] = None, args=(), kwargs={}, daemon: Union[bool, None] = None):
        return
