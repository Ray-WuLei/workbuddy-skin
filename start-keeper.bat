@echo off
chcp 65001 >nul
title WorkBuddy 皮肤守护 - 手动入口
setlocal

rem Override the interpreter with: set WBSKIN_PYTHON=C:\path\to\pythonw.exe
set "PYW=%WBSKIN_PYTHON%"
if not defined PYW set "PYW=%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\pythonw.exe"
if not exist "%PYW%" set "PYW=pythonw.exe"
set "KEEPER=%~dp0skin-watch.py"

start "" "%PYW%" "%KEEPER%"
echo.
echo   已发出启动指令。若守护已在运行，新实例会自动退出，不会重复。
echo   正常情况下无需手动运行：计划任务 WorkBuddySkinKeeper 会在登录时启动，
echo   并每 5 分钟检查一次。
echo.
ping -n 6 127.0.0.1 >nul
