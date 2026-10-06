@echo off
set "PATH=%LOCALAPPDATA%\Programs\MinGit\cmd;%PATH%"
echo ========================================================
echo Restoring SmartCollege ERP Database...
echo ========================================================
venv\Scripts\python.exe scripts\restore_db.py
echo ========================================================
pause
