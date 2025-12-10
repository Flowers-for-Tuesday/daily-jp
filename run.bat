@echo off
REM ==========================
REM 一键运行所有 Python 程序
REM ==========================

REM 保存当前目录
set BASE_DIR=%~dp0

echo ==========================
echo 运行 vocab\main.py
echo ==========================
cd /d "%BASE_DIR%vocab"
call python -u "main.py"

echo ==========================
echo 运行 listen\main.py
echo ==========================
cd /d "%BASE_DIR%listen"
call python -u "main.py"

echo ==========================
echo 运行 listen\sender.py
echo ==========================
cd /d "%BASE_DIR%listen"
call python -u "sender.py"

echo ==========================
echo 全部程序执行完毕
echo ==========================
pause
