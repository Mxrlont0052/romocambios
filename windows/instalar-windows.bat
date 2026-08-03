@echo off
REM ROMO CAMBIOS - instalador de Windows. Doble clic. Se corre UNA vez por PC.
REM El trabajo real lo hace instalar-windows.ps1; esto solo lo arranca sin que
REM Windows lo bloquee por la politica de scripts.
title ROMO CAMBIOS - instalador
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar-windows.ps1"
pause
