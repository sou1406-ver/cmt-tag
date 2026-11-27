@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Chua co moi truong .venv. Xem muc Demo web trong README.md.
    pause
    exit /b 1
)
if exist "outputs\06_Du_lieu_cuoi_V2\manifest.json" if exist "outputs\07_Mo_hinh_cuoi_V2\bert_modal_trained.json" (
    ".venv\Scripts\python.exe" -B -m src.web_demo --train-dir "outputs\06_Du_lieu_cuoi_V2" --bert-receipt "outputs\07_Mo_hinh_cuoi_V2\bert_modal_trained.json" --open
    if errorlevel 1 pause
    exit /b
)
".venv\Scripts\python.exe" -B -m src.web_demo --open
if errorlevel 1 pause
