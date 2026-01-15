@echo off
color 0A
echo =====================================
echo HR AUDIT BOT - DOUBLE CLICK START!
echo =====================================

:: Установка зависимостей
pip install discord.py

:: Открытие config.json для редактирования
notepad config.json

:: Начало работы бота
echo Starting bot...
python main.py
pause
