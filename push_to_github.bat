@echo off
set "PATH=%LOCALAPPDATA%\Programs\MinGit\cmd;%PATH%"
echo ========================================================
echo Pushing SmartCollege ERP to GitHub (ramesh8489/smartcollege)
echo ========================================================
git push -u origin main
echo ========================================================
echo Done! You can now close this window.
pause
