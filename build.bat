@echo off
rem 一键打包：产物在 dist\RYMachineDocKit\RYMachineDocKit.exe
python -m PyInstaller RYMachineDocKit.spec --noconfirm
if errorlevel 1 (
  echo.
  echo 打包失败，请先执行: pip install pyinstaller
  pause
  exit /b 1
)
echo.
echo 打包完成: dist\RYMachineDocKit\RYMachineDocKit.exe
pause
