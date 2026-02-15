@echo off
setlocal

set PROJECT_ID=suncheck-dashboard
set IMAGE_NAME=suncheck-bot
set SERVICE_NAME=suncheck-service
set REGION=us-central1

REM Build and Submit using Cloud Build (Simplest approach)
echo Submitting build...
call gcloud builds submit --tag gcr.io/%PROJECT_ID%/%IMAGE_NAME% .

REM Deploy
echo Deploying to Cloud Run...
call gcloud run deploy %SERVICE_NAME% ^
    --image gcr.io/%PROJECT_ID%/%IMAGE_NAME% ^
    --region %REGION% ^
    --platform managed ^
    --allow-unauthenticated ^
    --set-secrets POLY_ADDRESS=POLY_ADDRESS:latest,POLY_API_KEY=POLY_API_KEY:latest,POLY_SECRET=POLY_SECRET:latest,POLY_PASSPHRASE=POLY_PASSPHRASE:latest,POLY_PRIVATE_KEY=POLY_PRIVATE_KEY:latest

echo Deployment Complete!
call gcloud run services descrube %SERVICE_NAME% --region %REGION% --format "value(status.url)"
pause
