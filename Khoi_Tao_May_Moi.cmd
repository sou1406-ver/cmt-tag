@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"

if not exist ".venv\Scripts\python.exe" (
    py -3.12 -m venv .venv
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -m pip install -r requirements\classical-base.txt -r requirements\crawler.txt -r requirements\demo-transformers.txt modal==1.6.4
if errorlevel 1 goto failed

echo Da cai thu vien. Mo Mo_Demo.cmd de chay web.
echo De dung PhoBERT va ViSoBERT, dang nhap workspace Modal chua cac checkpoint:
echo .venv\Scripts\python.exe -m modal setup
pause
exit /b 0

:failed
echo Khoi tao that bai. Kiem tra Python 3.12 va ket noi Internet.
pause
exit /b 1
