@echo off
rem 一键打包：产物在 dist\RYMachineDocKit.exe（单文件，约 90MB）
setlocal
set PY=C:\Users\Administrator\.workbuddy\binaries\python\envs\rydoc\Scripts\python.exe
if not exist "%PY%" set PY=python

"%PY%" -m PyInstaller RYMachineDocKit.spec --noconfirm
if errorlevel 1 (
  echo.
  echo 打包失败，请先安装依赖: "%PY%" -m pip install pyinstaller -r requirements.txt
  pause
  exit /b 1
)
echo.
echo 打包完成: dist\RYMachineDocKit.exe
pause
