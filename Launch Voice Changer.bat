@echo off
setlocal

set "app_dir=%~dp0dist\windows-cuda\MMVCServerSIO"
if not exist "%app_dir%\MMVCServerSIO.exe" (
    echo Voice Changer executable was not found at:
    echo "%app_dir%\MMVCServerSIO.exe"
    pause
    exit /b 1
)

cd /d "%app_dir%" || exit /b 1
".\MMVCServerSIO.exe"
