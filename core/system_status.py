import psutil


def get_realtime_status() -> dict:
    return {
        "cpu_percent": round(psutil.cpu_percent(interval=0.3), 1),
        "memory_percent": round(psutil.virtual_memory().percent, 1),
        "disk_percent": round(psutil.disk_usage("C:\\").percent, 1),
    }
