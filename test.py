# import inspect
# from typing import Optional, Union

# def hello(one, two, three: int, four = 4, five: int = 5, **kwargs):
#     return

# def hello2(one, two: str, three: Optional[int], four = 4, five: Union[int, float] = 5, **kwargs):
#     return
#
# sig = inspect.signature(hello2)
# print(sig)

# for item in sig.parameters.values():
#     print("Arg name: {}".format(item.name))
#     print("Arg default: {}".format(item.default))
#     if item.default == inspect.Parameter.empty:
#         print("empty")
#     else:
#         print("not empty")
#     print("Arg annotation: {}".format(item.annotation))
#     print("Arg type(annotation): {}".format(type(item.annotation)))
#     if item.annotation == inspect.Parameter.empty:
#         print("annotation is None")
#     elif type(item.default) is type:
#         print("annotation is {}".format(item.annotation))
#     elif item.annotation.__module__ is "typing":
#         print("annotation is {}".format(item.annotation.__args__))
#         for t in item.annotation.__args__:
#             print("{}: {}".format(t, type(t)))
#     print("Arg kind: {}".format(item.kind))
#     print("")

# print("Union[int, float]: {}".format(Union[int, float]))
# print("type(Union[int, float]): {}".format(type(Union[int, float])))
# if type(Union[int, float]) is type:
#     print("Union[int, float] is a type")
# for item, val in vars(Union[int, float]).items():
#     print("{}: {}".format(item, val))
#     if item == "__module__" and val == "typing":
#         print("true")
# print("")

# print("Optional[int]: {}".format(Optional[int]))
# print("type(Optional[int]): {}".format(type(Optional[int])))
# if type(Optional[int]) is type:
#     print("Optional[int] is a type")
# for item in dir(Optional[int]):
#     print("{}: {}".format(item, val))
#     if item == "__module__" and val == "typing":
#         print("true")
# print("")
# for arg in Optional[int].__args__:
#     print(arg)

try:
    import win32com.client
    winmgmts_root = win32com.client.GetObject("winmgmts:root\\cimv2")
    cpus = winmgmts_root.ExecQuery("Select * from Win32_Processor")
    cpu_vars = [
        "AddressWidth",
        "Architecture",
        "AssetTag",
        "Availability",
        "Caption",
        "Characteristics",
        "ConfigManagerErrorCode",
        "ConfigManagerUserConfig",
        "CreationClassName",
        "CurrentClockSpeed",
        "CurrentVoltage",
        "DataWidth",
        "Description",
        "DeviceID",
        "ErrorCleared",
        "ErrorDescription",
        "ExtClock",
        "Family",
        "InstallDate",
        "L2CacheSize",
        "L2CacheSpeed",
        "L3CacheSize",
        "L3CacheSpeed",
        "LastErrorCode",
        "Level",
        "LoadPercentage",
        "Manufacturer",
        "MaxClockSpeed",
        "Name",
        "NumberOfCores",
        "NumberOfEnabledCore",
        "NumberOfLogicalProcessors",
        "OtherFamilyDescription",
        "PartNumber",
        "PNPDeviceID",
        "PowerManagementCapabilities",
        "PowerManagementSupported",
        "ProcessorId",
        "ProcessorType",
        "Revision",
        "Role",
        "SecondLevelAddressTranslationExtensions",
        "SerialNumber",
        "SocketDesignation",
        "Status",
        "StatusInfo",
        "Stepping",
        "SystemCreationClassName",
        "SystemName",
        "ThreadCount",
        "UniqueId",
        "UpgradeMethod",
        "Version",
        "VirtualizationFirmwareEnabled",
        "VMMonitorModeExtensions",
        "VoltageCaps"
    ]
    for cpu in cpus:
        for item in cpu_vars:
            print("{}: {}".format(item, getattr(cpu, item)))
except ImportError as ie:
    print(ie)
print("")
# gpus = winmgmts_root.ExecQuery("Select * from Win32_VideoController")
# gpu_vars = [
#     "AcceleratorCapabilities",
#     "AdapterCompatibility",
#     "AdapterDACType",
#     "AdapterRAM",
#     "Availability",
#     "CapabilityDescriptions",
#     "Caption",
#     "ColorTableEntries",
#     "ConfigManagerErrorCode",
#     "ConfigManagerUserConfig",
#     "CreationClassName",
#     "CurrentBitsPerPixel",
#     "CurrentHorizontalResolution",
#     "CurrentNumberOfColors",
#     "CurrentNumberOfColumns",
#     "CurrentNumberOfRows",
#     "CurrentRefreshRate",
#     "CurrentScanMode",
#     "CurrentVerticalResolution",
#     "Description",
#     "DeviceID",
#     "DeviceSpecificPens",
#     "DitherType",
#     "DriverDate",
#     "DriverVersion",
#     "ErrorCleared",
#     "ErrorDescription",
#     "ICMIntent",
#     "ICMMethod",
#     "InfFilename",
#     "InfSection",
#     "InstallDate",
#     "InstalledDisplayDrivers",
#     "LastErrorCode",
#     "MaxMemorySupported",
#     "MaxNumberControlled",
#     "MaxRefreshRate",
#     "MinRefreshRate",
#     "Monochrome",
#     "Name",
#     "NumberOfColorPlanes",
#     "NumberOfVideoPages",
#     "PNPDeviceID",
#     "PowerManagementCapabilities",
#     "PowerManagementSupported",
#     "ProtocolSupported",
#     "ReservedSystemPaletteEntries",
#     "SpecificationVersion",
#     "Status",
#     "StatusInfo",
#     "SystemCreationClassName",
#     "SystemName",
#     "SystemPaletteEntries",
#     "TimeOfLastReset",
#     "VideoArchitecture",
#     "VideoMemoryType",
#     "VideoMode",
#     "VideoModeDescription",
#     "VideoProcessor"
# ]
# for gpu in gpus:
#     for item in gpu_vars:
#         print("{}: {}".format(item, getattr(gpu, item)))

from asyncproc import asyncproc
if __name__ == "__main__":
    inst = asyncproc()
    for k, v in vars(inst).items():
        print("{}: {}".format(k, v))
