@echo off
setlocal
cd /d "%~dp0"
set "PYTHON_EXE=C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe"
set "QT_QPA_PLATFORM=windows"
set "QT_QPA_PLATFORM_PLUGIN_PATH=C:\Users\Administrator\AppData\Local\Programs\Python\Python314\Lib\site-packages\PyQt5\Qt5\plugins\platforms"
set "QT_PLUGIN_PATH=C:\Users\Administrator\AppData\Local\Programs\Python\Python314\Lib\site-packages\PyQt5\Qt5\plugins"
set "PATH=C:\Users\Administrator\AppData\Local\Programs\Python\Python314\Lib\site-packages\PyQt5\Qt5\bin;%PATH%"
"%PYTHON_EXE%" main.py
pause
