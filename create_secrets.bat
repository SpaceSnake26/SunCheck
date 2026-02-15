@echo off
setlocal enabledelayedexpansion

REM Set project ID if known, otherwise use gcloud config
REM set PROJECT_ID=your-project-id

echo Creating secrets from .env file...

for /f "tokens=1,2 delims==" %%a in (src\.env) do (
    set "key=%%a"
    set "value=%%b"
    
    REM Clean up quotes if present
    set "value=!value:"=!"
    
    echo Creating secret: !key!
    
    REM Create secret (ignore error if exists)
    call gcloud secrets create !key! --replication-policy="automatic" 2>nul
    
    REM Add version
    echo !value! | call gcloud secrets versions add !key! --data-file=-
)

echo Done creating secrets.
pause
