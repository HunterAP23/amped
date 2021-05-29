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


class asyncproc_function:
    def __init__(self, name: str, pointer: Callable, instances: Union[list[int], set[int], tuple[int]]):
        if callable(pointer):
            self.name = name
            self.pointer = pointer
            self.instances = list(set(instances))
            self.arguments = {}
            params = inspect.signature(pointer).parameters
            for item in params.values():
                self.arguments[item.name] = {
                    "annotation": item.annotation,
                    "kind": item.kind
                }
                if item.default == inspect.Parameter.empty:
                    self.arguments[item.name]["default"] = None
                else:
                    self.arguments[item.name]["default"] = item.default

                if item.annotation == inspect.Parameter.empty:
                    self.arguments[item.name]["type"] = None
                elif type(item.default) is type:
                    self.arguments[item.name]["type"] = item.annotation
                elif item.annotation.__module__ == "typing":
                    self.arguments[item.name]["type"] = []
                    for t in item.annotation.__args__:
                        self.arguments[item.name]["type"].append(t)
                    self.arguments[item.name]["type"] = tuple(set(self.arguments[item.name]["type"]))
        else:
            raise TypeError("Function pointer is not callable.")

    def get(self):
        return vars(self)


class asyncproc_argument:
    def __init__(self, name: str, value: Any, arg_type: type, function_name: str):
        self.name = name
        self.value = value,
        self.type = arg_type
        self.function = function_name

    def get(self):
        return vars(self)


class asyncproc_error(Exception):
    pass


class asyncproc:
    def __init__(self, log: Union[lg.RootLogger, None] = None, procs: Union[list[int], set[int], tuple[int], None] = None, threads: Union[list[int], set[int], tuple[int], None] = None):
        """
        Class for creating and managing multiple processes and threads, with the ability to run them asynchronously.

        Parameters
        ----------
        log : logging.RootLogger, None
            A logging.RootLogger object to use for logging purposes.
            If None, then the logging messages will be printed to the console.
        procs : list[int], set[int], tuple[int], None
            A list/set/tuple of integers.
            The integers
        sound : str
            the sound that the animal makes
        num_legs : int
            the number of legs the animal has (default 4)
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

        self._processes = None
        self._threads = None
        if self.set_procs(procs):
            self._processes = procs
        else:
            self._processes = [0]

        if self.set_threads(threads):
            self._threads = threads
        else:
            self._threads = [0]

    def _get_info_freebsd(self):
        int(os.popen("sysctl -n hw.ncpu").readlines()[0])

    def _get_info_linux(self):
        self._cores_usable = os.sched_getaffinity(0)
        self._cores_usable_count = len(self._cores_usable)
        sockets = []
        physical_cores = []
        logical_cores = []
        cores_id = []
        with open("/proc/cpuinfo") as cpu_info:
            for line in [line.split(":") for line in cpu_info.readlines()]:
                if (line[0].strip() == "physical id"):
                    sockets.append(int(line[1].strip()))
                elif (line[0].strip() == "cpu cores"):
                    physical_cores.append(int(line[1].strip()))
                elif (line[0].strip() == "siblings"):
                    logical_cores.append(int(line[1].strip()))
                elif (line[0].strip() == "core id"):
                    cores_id.append((line[1].strip()))

        self._sockets_count = len(set(sockets))
        self._cores_physical = sorted(set(physical_cores))
        self._cores_logical = sorted(set(logical_cores))

    # INCOMPLETE - NEEDS TESTING ON MAC OS
    def _get_info_macos(self):
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

    def _get_info_windows(self):
        tmp = sys.getwindowsversion()
        self._windows_version_major = tmp.major
        self._windows_version_minor = tmp.minor
        self._windows_version_build = tmp.build
        self._windows_version_platform = tmp.platform
        self._windows_version_service_pack = tmp.service_pack

        # Get simultaneous multithreading info
        # https://docs.microsoft.com/en-us/windows/win32/cimwin32prov/win32-processor
        winmgmts_root = win32com.client.GetObject("winmgmts:root\\cimv2")
        cpus = winmgmts_root.ExecQuery("Select * from Win32_Processor")
        for cpu in cpus:
            self._sockets_count += 1
            self._cores_physical.append(cpu.NumberOfCores)
            self._cores_logical.append(cpu.NumberOfLogicalProcessors)
            if cpu.NumberOfCores < cpu.NumberOfLogicalProcessors:
                self._smt.append(True)

        # Get affinity info
        handle = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, True, self._pid)
        mask = win32process.GetProcessAffinityMask(handle)
        mask_proc = mask[0]
        mask_sys = mask[1]
        bitmask_proc = "{0:08b}".format(mask_proc)
        bitmask_sys = "{0:08b}".format(mask_sys)

        temp_cores_proc = []
        temp_cores_sys = []

        for i in range(len(bitmask_proc)):
            x = list(reversed(bitmask_proc))[i]
            if int(x):
                temp_cores_proc.append(i)

        for i in range(len(bitmask_sys) - 1, -1, -1):
            x = list(reversed(bitmask_sys))[i]
            if int(x):
                temp_cores_sys.append(i)

        self._cores_usable = set(temp_cores_proc)
        self._cores_usable_sys = set(temp_cores_sys)
        self._cores_usable_count = len(self._cores_usable)

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

    def _test_callable(self, method: Callable, name: str):
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

    def _validate_threads_processes(self, threads: Union[int, None] = None, processes: Union[int, None] = None) -> bool:
        tmp_threads = None
        tmp_procs = None
        if threads:
            tmp_threads = threads
        elif self._threads:
            tmp_threads = self._threads
        else:
            tmp_threads = [0]

        if processes:
            tmp_procs = processes
        elif self._processes:
            tmp_procs = self._processes
        else:
            tmp_procs = [0]

        if len(tmp_threads) * len(tmp_procs) > self._cores_usable_count:
            return False
        return True

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

    def set_affinity(self, affinity: Union[list, tuple]) -> bool:
        # Remove duplicate entries
        new_affinity = set(affinity)

        # Make sure there are elements
        if len(new_affinity) == 0:
            return False

        # Get rid of any elements greater than the highest core number
        while max(new_affinity) > max(self._cores_usable):
            new_affinity.discard(max(new_affinity))

        # Make sure there are no entries less than 0
        while 0 in new_affinity:
            new_affinity.discard(min(new_affinity))

        # Make sure we still have elements after removing the above values
        if len(new_affinity) == 0:
            return False

            self._cores_usable = tuple(new_affinity)
            return True

    def get_cores_count(self) -> int:
        return self._core_count

    def get_pid(self) -> int:
        return self._pid

    def get_sys_platform(self) -> str:
        return self._sys_platform

    def get_threads(self) -> int:
        return self._threads

    def set_threads(self, threads: Union[list[int], set[int], tuple[int]]) -> bool:
        if self._validate_threads_processes(threads=threads):
            self._threads = threads
            return True
        return False

    def get_procs(self) -> int:
        return self._processes

    def set_procs(self, processes: Union[list[int], set[int], tuple[int]]) -> bool:
        if self._validate_threads_processes(processes=processes):
            self._processes = processes
            return True
        return False

    def get_funcs(self) -> Union[dict, list, set, tuple]:
        return self._funcs

    def set_funcs(self, funcs: Union[dict, list, set, tuple]) -> bool:
        if type(funcs) in (list, tuple):
            self._funcs = set()
        return True

    def add_funcs(self, funcs: Union[dict, list, set, tuple]) -> bool:
        return True

    def get_args(self) -> Union[dict, list, set, tuple]:
        return self._args

    def set_args(self, args: Union[dict, list, set, tuple]) -> bool:
        return True

    def create_argument(self, name: str, value, val_type: Optional, instances: Union[list[int], set[int], tuple[int]]) -> dict:
        arg = {
            "Name": name,
            "Value": value
        }

        if val_type is not None:
            arg["Type"] = val_type
        else:
            arg["Type"] = type(arg["Value"])

        instances_tmp = []
        try:
            for inst in sorted(set(instances)):
                if type(inst) is int:
                    instances_tmp
                else:
                    raise TypeError("Instance number {} is not an integer.".format(inst))
        except TypeError as te:
            if self._log is not None:
                self._log.error(te)
            else:
                print(te)
        arg["Instances"] = instances_tmp

        return arg

    def create_function(self, name: str, pointer: Callable, instances: int) -> dict:
        func = {
            "Name": name,
            "Instances": instances
        }

        try:
            if callable(pointer):
                func["Pointer"] = pointer
            else:
                raise NameError("Function {} does not exist.".format(name))
        except NameError as ne:
            if self._log is not None:
                self._log.error(ne)
            else:
                print(ne)

        func["Arguments"] = {}
        args_params = inspect.signature(pointer).parameters
        for item in args_params.values():
            func["Arguments"][item.name] = {}

            if item.default == inspect.Parameter.empty:
                func["Arguments"][item.name]["default"] = None
            else:
                func["Arguments"][item.name]["default"] = item.default

            if item.annotation == inspect.Parameter.empty:
                func["Arguments"][item.name]["type"] = None
            elif type(item.default) is type:
                func["Arguments"][item.name]["type"] = item.annotation
            elif "__module__" in dir(item.annotation) and item.annotation.__module__ == "typing":
                func["Arguments"][item.name]["type"] = item.annotation.__args__
        return func

    def create_group(self):
        return


# if __name__ == "__main__":
#     inst = asyncproc()
#     for k, v in vars(inst).items():
#         print("{}: {}".format(k, v))
