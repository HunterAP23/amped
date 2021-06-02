# Process related
import asyncio
import multiprocessing as mp
import multiprocessing.dummy as mpd
import subprocess as sp

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

# Miscellaneous
from typing import Any, Callable, Optional, Union

if sys.platform.startswith("win32"):
    try:
        import win32api
        import win32com
        import win32com.client
        import win32con
        import win32process
    except ModuleNotFoundError as mnfe:
        print(mnfe)
        exit(1)


class asyncproc_argument:
    def __init__(self, name: str, value: Any, arg_type: type, function_name: str):
        self.name = name
        self.value = value,
        self.type = arg_type
        self.function = function_name

    def get(self) -> dict:
        return vars(self)


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

    def __init__(self, cores: Union[int, list[int], set[int], tuple[int], None] = None, log: Union[lg.RootLogger, None] = None):
        """
        Contructs the asyncproc object and collects system information.

        Parameters
        ----------
            cores : int, list[int], tuple[int], None
                An int or list/set/tuple of integers which represents the CPU core affinity to use.
                If it's an integer, it should be the total number of CPU cores to utilize with no preference for CPU core affinity.
                If it's a list/set/tuple, it should contain integers specifiying which cores to utilize specifically.
                The range should from 0 to the max number of cores on the system.
                Values less than 0 or greater than the max core number are truncated, and duplicate entrieis are removed.
                If the value is None then the program will automatically use all the cores it can.

            log : logging.RootLogger, None
                A logging.RootLogger object to use for logging purposes.
                If None, then the logging messages will be printed to the console.
        """

        if log is not None:
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

        # Save this Python process' PID for future use.
        self._pid = os.getpid()
        # Get the reported number of CPU cores
        self._cores_count = mp.cpu_count()
        # For saving count of CPU sockets in systems, mostly for multi-socket use
        self._sockets_count = 0
        # Which cores are usable, based on the affinity for this process
        self._cores_usable = None
        # Number of usable cores
        self._cores_usable_count = None
        # List of physical cores - typically even numbered starting at 0
        self._cores_physical = []
        # List of logical cores - typically odd numbered starting at 1
        self._cores_logical = []
        # Whether the system has Simultaneous Multithreading / Hyperthreading
        # This is a list for measuring SMT on multiple sockets,
        self._smt = []
        if sys.platform.startswith("freebsd"):
            self._sys_platform = "FreeBSD"
        elif sys.platform.startswith("linux"):
            self._sys_platform = "Linux"
            self._get_info_linux()
        elif sys.platform.startswith("aix"):
            self._sys_platform = "AIX"
        elif sys.platform.startswith("win32"):
            self._sys_platform = "Windows"
            self._get_info_windows()
        elif sys.platform.startswith("darwin"):
            self._sys_platform = "MacOS"
            self._get_info_macos()

        self._cores_user = None
        self._cores_user_count = None
        if cores is None or len(cores) >= self._cores_usable_count:
            pass
        elif 0 < len(cores) and len(cores) <= self._cores_usable_count:
            self._cores_user = list(set(cores))
            self._cores_user_count = len(self._cores_user)
        else:
            self._cores_user = [0]

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
        self._cores_usable = tuple(os.sched_getaffinity(0))
        self._cores_usable_count = len(self._cores_usable)

        dict_lscpu = dict()
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
        self._cores_usable_count = dict_lscpu["CPU(s)"]
        self._smt = int(dict_lscpu["Thread(s) per core"]) > 1
        self._model_name = dict_lscpu["Model name"]

    # INCOMPLETE - NEEDS TESTING ON MAC OS
    def _get_info_macos(self) -> None:
        tmp_dict = dict()
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
        mask_proc = mask[0]
        mask_sys = mask[1]
        affinity_proc = self.mask_to_affinity(self.int_to_mask(str(mask_proc)), tuple)
        affinity_sys = self.mask_to_affinity(self.int_to_mask(str(mask_sys)))

        self._cores_usable = affinity_proc
        self._cores_usable_count = len(self._cores_usable)

    def int_to_mask(self, int_val: Union[int, str], return_type: Union[type[list, str, tuple], None] = None) -> Union[list, tuple, str]:
        ret = "{0:08b}".format(int(int_val))

        if return_type is None or return_type == list:
            return list(i for i in list(ret))
        elif return_type == tuple:
            return tuple(i for i in list(ret))
        elif return_type == str:
            return ret

    def mask_to_int(self, mask: Union[int, str, list, tuple], return_type: Union[type[int, list, set, str, tuple], None] = None) -> Union[int, list, set, str, tuple]:
        if type(mask) in (int, str):
            mask = list(str(mask))
        ret = "".join(mask)

        if return_type == int:
            return int(ret, 2)
        elif return_type == list or return_type is None:
            return list(i for i in ret)
        elif return_type == set:
            return set(ret)
        elif return_type == str:
            return ret
        elif return_type == tuple:
            return tuple(i for i in ret)

    def mask_to_affinity(self, mask: Union[list, set, tuple], return_type: Union[type[list, set, tuple], None] = None) -> Union[list, set, tuple]:
        if type(mask) in (int, str):
            mask = list(str(mask))
        mask_reversed = list(reversed(list(mask)))
        ret = tuple(i for i in range(len(mask_reversed)) if int(mask_reversed[i]) == 1)

        if return_type is None or return_type == list:
            return list(ret)
        elif return_type == set:
            return set(ret)
        elif return_type == tuple:
            return ret

    def affinity_to_mask(self, affinity: Union[list, set, str, tuple], return_type: Union[type[str, list, tuple], None] = None) -> Union[list, tuple, str]:
        affinity_list = list(affinity)
        mask_list = []
        start = 0
        while True:
            if len(affinity_list) == 0:
                break
            min_val = min(affinity_list)
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
        if return_type is None or return_type == list:
            return mask_reversed
        elif return_type == tuple:
            return tuple(mask_reversed)
        elif return_type == str:
            return "".join(str(i) for i in mask_reversed)

    def _run_in_parallel(self, functions: Union[dict, list, tuple], arguments: Union[dict, list, tuple], threads: int, sema: mp.Semaphore, rlock: mp.RLock, no_args: bool = False):
        # proc = []
        # for func in funcs:
        #     p = mp.Process(target=self._time_function, args=(func, args[func], sema, rlock))
        #     proc.append(p)
        #
        # for p in proc:
        #     p.start()
        #
        # for p in proc:
        #     try:
        #         p.join()
        #     except Exception as e:
        #         self._log.error(e)
        funcs_data = dict()
        args_data = dict()
        try:
            # Handle functions
            funcs_items = []
            if len(functions) == 0:
                raise IndexError("No functions were given.")
            elif type(functions) is dict:
                funcs_items = [(name, func) for name, func in functions.items()]
            elif type(functions) in (list, tuple):
                for item in functions:
                    # Expect pair of "name, function" as a dict, list, or tuple
                    if type(item) not in (dict, tuple, list):
                        raise TypeError("Function list contains a non-iterable element (requires a dict, list, or tuple).")
                funcs_items = [(name, func) for name, func in item]
            for name, func in funcs_items:
                if self._test_callable(name, func):
                    funcs_data[name] = dict()
                    funcs_data[name]["Function"] = func
            if len(funcs_data) == 0:
                raise IndexError("None of the given functions are callable.")

            # Handle arguments
            args_items = []
            if not self._no_args and len(arguments) == 0:
                raise IndexError("User specified that arguments are required but did no arguments were given.")
            elif type(arguments) is dict:
                args_items = [(name, value) for name, value in arguments.items()]
            elif type(arguments) in (list, tuple):
                for item in arguments:
                    # Expect pair of "name, function" as a dict, list, or tuple
                    if type(item) not in (dict, tuple, list):
                        raise TypeError("Argument list contains a non-iterable element (requires a dict, list, or tuple).")
                    elif type(item) is dict:
                        args_items = [(name, value) for name, value in item]
                    elif type(item) in (list, tuple):
                        args_items = [(name, value) for name, value in item]
            for name, func in args_items:
                if self._test_callable(name, func):
                    args_data[name] = dict()
                    args_data[name]["Function"] = func
            if len(funcs_data) == 0:
                raise IndexError("None of the given functions are callable.")
        except IndexError as ie:
            if self._log is not None:
                self._log.critical(ie)
            else:
                print(ie)
            exit(1)

        self._run_map(func)

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

    def _time_function(self, func, args: Union[dict, list, set, tuple], sema, rlock) -> bool:
        ret = dict()
        ret["Success"] = False
        was_acquired = False
        try:
            was_acquired = True
            sema.acquire()
            ret["return"] = func(**args, sema=sema)
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
            else:
                print(e)
            return ret

    def create_pool(self):
        check = (self._procs is None, self._procs == 0)
        if self._cores_usable_count is not None:
            if any(check) or self._procs >= self._core_count:
                self._pool_proc = mp.pool.Pool(self._core_count)
            elif len(self._processes) < self._core_count:
                if self._processes == [0]:
                    self._processes = [1]
                try:
                    self._pool_proc = mp.Pool(self._processes)
                except Exception as e:
                    if self._log is not None:
                        self._log.error(e)
                    else:
                        print(e)
        else:
            if any(check) or self._cores_count >= self._cores_usable_count:
                self._pool_proc = mp.Pool(self._cores_usable_count)
            elif self._cores_count < self._cores_usable_count:
                self._pool_proc = mp.Pool(self._cores_count)

    def get_affinity(self) -> Union[list, set, tuple]:
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

    def get_cores_count(self) -> int:
        return self._core_count

    def get_pid(self) -> int:
        return self._pid

    def get_sys_platform(self) -> str:
        return self._sys_platform

    def create_process_pool(self, processes: Union[int, None] = None, function: Union[Callable, None] = None, args: Union[dict, list, set, tuple, None] = None):
        return

    def create_process(self, function: Union[Callable, None] = None, args: Union[dict, list, set, tuple, None] = None):
        return

    def create_process_pool(self, threads: Union[int, None] = None, function: Union[Callable, None] = None, args: Union[dict, list, set, tuple, None] = None):
        return

    def create_thread(self, function: Union[Callable, None] = None, args: Union[dict, list, set, tuple, None] = None):
        return
