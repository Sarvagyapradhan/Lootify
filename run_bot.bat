@echo off
title Clash of Clans Farming Bot
color 0A
echo ====================================================================
echo                CLASH OF CLANS AUTOMATION BOT
echo ====================================================================
echo.

if exist "CocBot.exe" (
    echo Launching compiled executable CocBot.exe...
    "CocBot.exe"
) else if exist "dist\CocBot.exe" (
    echo Launching compiled executable dist\CocBot.exe...
    "dist\CocBot.exe"
) else (
    echo Executable not found. Running Python source main.py...
    python main.py
)

pause
