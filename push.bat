@echo off
cd /d %~dp0

git add .

if "%~1"=="" (
    git commit -m "Update"
) else (
    git commit -m "%~1"
)

git push origin main

echo.
echo Done. Vercel will auto-redeploy in a minute - check vercel.com dashboard.
pause
