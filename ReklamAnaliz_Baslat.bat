@echo off
setlocal
title ReklamAnaliz Baslatiliyor

set "ROOT_DIR=%~dp0"
if not exist "%ROOT_DIR%start_dev_stack.ps1" goto :missing
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT_DIR%start_dev_stack.ps1"
if errorlevel 1 goto :failed

exit /b 0

:missing
echo HATA: start_dev_stack.ps1 bulunamadi.
pause
exit /b 1

:failed
echo HATA: Baslatma tamamlanamadi. Yukaridaki hatayi ve runtime\launcher loglarini kontrol edin.
pause
exit /b 1
