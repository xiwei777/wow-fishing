@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0\.."
if "%~1"=="" (
  echo 请指定权重文件，例如 scripts\build_windows.bat models\best_v4.pt
  pause
  exit /b 1
)
if not exist .venv\Scripts\python.exe (
  py -3.10 -m venv .venv
  if errorlevel 1 goto failed
)
.venv\Scripts\python.exe -m pip install torch==2.10.0 torchvision==0.25.0 --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
if errorlevel 1 goto failed
.venv\Scripts\python.exe scripts\build_app.py --model "%~1"
if errorlevel 1 goto failed
echo 构建完成，程序在 release 目录。
pause
exit /b 0
:failed
echo 构建失败，请保留上面的报错信息。
pause
exit /b 1
