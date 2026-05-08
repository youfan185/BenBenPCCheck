import platform
import socket
from dataclasses import dataclass, asdict

import psutil


@dataclass
class CPUInfo:
    name: str
    physical_cores: int
    logical_cores: int
    current_usage_percent: float


@dataclass
class MemoryInfo:
    total_gb: float
    used_gb: float
    available_gb: float
    usage_percent: float


def get_system_info() -> dict:
    return {
        "computer_name": platform.node(),
        "user_name": platform.uname().node,
        "os_name": platform.system(),
        "os_version": platform.version(),
        "system_type": platform.machine(),
        "hostname": socket.gethostname(),
    }


def get_cpu_info() -> dict:
    name = platform.processor() or "Unknown CPU"
    info = CPUInfo(
        name=name,
        physical_cores=psutil.cpu_count(logical=False) or 0,
        logical_cores=psutil.cpu_count(logical=True) or 0,
        current_usage_percent=round(psutil.cpu_percent(interval=0.4), 1),
    )
    return asdict(info)


def get_memory_info() -> dict:
    vm = psutil.virtual_memory()
    info = MemoryInfo(
        total_gb=round(vm.total / (1024**3), 1),
        used_gb=round(vm.used / (1024**3), 1),
        available_gb=round(vm.available / (1024**3), 1),
        usage_percent=round(vm.percent, 1),
    )
    return asdict(info)
