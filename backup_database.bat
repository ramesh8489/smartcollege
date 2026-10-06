@echo off
set "PATH=%LOCALAPPDATA%\Programs\MinGit\cmd;%PATH%"
echo ========================================================
echo Backing up SmartCollege ERP Database...
echo ========================================================
venv\Scripts\python.exe scripts\backup_db.py
echo ========================================================
pause
