@echo off
setlocal EnableExtensions
title Lua Deobfuscator (FiveM)
cd /d "%~dp0"

rem ---- Tim Python ----------------------------------------------------------
set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY where py >nul 2>nul && set "PY=py -3"
if not defined PY goto no_python

rem ---- Lay duong dan: keo-tha vao file .bat, hoac chon / dan duong dan --------
set "SRC=%~1"
if defined SRC goto check_src

:menu
echo.
echo  ============================================
echo     LUA DEOBFUSCATOR - FiveM (L0_1, A0_2 ...)
echo  ============================================
echo   1. Chon thu muc bang cua so
echo   2. Dan duong dan thu muc hoac file .lua
echo   3. Thoat
echo.
choice /c 123 /n /m "  Chon 1, 2 hoac 3: "
if errorlevel 3 exit /b 0
if errorlevel 2 goto ask_path

set "SRC="
for /f "usebackq delims=" %%I in (`powershell -NoProfile -STA -Command "Add-Type -AssemblyName System.Windows.Forms; $d = New-Object System.Windows.Forms.FolderBrowserDialog; $d.Description = 'Chon thu muc chua cac file .lua'; if ($d.ShowDialog() -eq 'OK') { $d.SelectedPath }"`) do set "SRC=%%I"
if defined SRC goto check_src
echo   Ban chua chon thu muc nao.
goto menu

:ask_path
set "SRC="
set /p "SRC=  Dan duong dan: "
if not defined SRC goto menu
set "SRC=%SRC:"=%"

:check_src
if "%SRC:~-1%"=="\" set "SRC=%SRC:~0,-1%"
if not exist "%SRC%" goto not_found
if exist "%SRC%\*" goto is_folder

rem ---- Mot file .lua --------------------------------------------------------
for %%F in ("%SRC%") do set "OUT=%%~dpnF_deobf.lua"
echo.
echo   Dang xu ly file: %SRC%
%PY% -m lua_deobf "%SRC%" -o "%OUT%" --report
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" goto failed
echo   XONG! Ket qua: %OUT%
echo   Bao cao   : %OUT:~0,-4%.report.md
explorer /select,"%OUT%"
goto end

rem ---- Ca thu muc (xu ly tat ca file .lua, ke ca thu muc con) ---------------
:is_folder
set "OUT=%SRC%_deobf"
echo.
echo   Dang xu ly thu muc: %SRC%
echo   Ket qua se luu vao: %OUT%
echo.
%PY% -m lua_deobf "%SRC%" -o "%OUT%" --report
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" goto failed
echo   XONG! Tat ca file da duoc luu trong: %OUT%
echo   (moi file .lua co them file .report.md giai thich)
explorer "%OUT%"
goto end

:failed
echo   CO LOI xay ra - xem thong bao phia tren.
echo   (VERIFICATION FAILED: khong nen dung file do; syntax error: file khong phai Lua hop le / la bytecode)
goto end

:not_found
echo.
echo   Khong tim thay: %SRC%
set "SRC="
goto menu

:no_python
echo.
echo   Khong tim thay Python!
echo   Hay cai Python 3 tu https://www.python.org/downloads/
echo   (nho tich o "Add Python to PATH" khi cai), roi chay lai file nay.
goto end

:end
echo.
pause
