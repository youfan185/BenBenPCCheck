import os
import sys
from pathlib import Path


def configure_qt() -> None:
    import PyQt5

    qt_root = Path(PyQt5.__file__).resolve().parent / "Qt5"
    qt_bin = qt_root / "bin"
    qt_plugins = qt_root / "plugins"
    platforms = qt_plugins / "platforms"

    os.environ.pop("QT_PLUGIN_PATH", None)
    os.environ.pop("QT_QPA_PLATFORM_PLUGIN_PATH", None)
    os.environ["QT_QPA_PLATFORM"] = "windows"

    if platforms.exists():
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(platforms)

    if qt_plugins.exists():
        os.environ["QT_PLUGIN_PATH"] = str(qt_plugins)

    if qt_bin.exists():
        os.environ["PATH"] = str(qt_bin) + os.pathsep + os.environ.get("PATH", "")
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(str(qt_bin))
