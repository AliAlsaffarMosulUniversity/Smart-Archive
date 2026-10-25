@echo off
setlocal
cd /d "%~dp0"
py -3 -m venv .venv
if errorlevel 1 goto fail
.venv\Scripts\python -m pip install -r requirements.txt
if errorlevel 1 goto fail
.venv\Scripts\python tools\prepare_model.py
if errorlevel 1 goto fail
.venv\Scripts\python tools\prepare_ocr.py
if errorlevel 1 goto fail
.venv\Scripts\python -m unittest discover -s tests -v
if errorlevel 1 goto fail
.venv\Scripts\python -m PyInstaller --noconfirm --clean --windowed --onedir --name SmartArchive --collect-all pypdf --collect-all docx --collect-all openpyxl --collect-all pptx --collect-all PIL --collect-all pypdfium2 --collect-all pypdfium2_raw --collect-all onnxruntime --collect-all tokenizers --add-data "ocr;ocr" --add-data "models;models" app.py
if errorlevel 1 goto fail
echo Build ready: dist\SmartArchive\SmartArchive.exe
where ISCC >nul 2>nul
if errorlevel 1 goto noinstaller
ISCC installer\SmartArchive.iss
if errorlevel 1 goto fail
goto done
:noinstaller
echo Optional: install Inno Setup and compile installer\SmartArchive.iss
:done
pause
exit /b 0
:fail
echo BUILD FAILED. See error above.
pause
exit /b 1
