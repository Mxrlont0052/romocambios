@echo off
REM Doble clic para abrir ROMO CAMBIOS en el navegador (Windows).
REM Es el equivalente de "ROMO CAMBIOS.command" en la Mac.
setlocal
title ROMO CAMBIOS

REM Para cambiar el puerto, quita el REM de la linea de abajo:
REM set ROMOCAMBIOS_PORT=8899

cd /d "%~dp0web"
if errorlevel 1 (
  echo No encontre la carpeta "web" al lado de este archivo.
  pause
  exit /b 1
)

REM "py" es el lanzador que instala python.org. Si no esta, se prueba "python".
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"

if not defined PY (
  echo.
  echo   No encontre Python en esta computadora.
  echo   Corre primero  instalar-windows.bat
  echo.
  pause
  exit /b 1
)

%PY% server.py

REM Si el servidor murio de una (puerto ocupado, falta ffmpeg), el error queda
REM a la vista en vez de cerrarse la ventana en la cara.
if errorlevel 1 (
  echo.
  echo   La app se cerro con un error. El texto de arriba dice por que.
  pause
)
