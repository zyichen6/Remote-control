@echo off
chcp 65001 >nul
title 远程控制系统 - 安装依赖

echo ============================================================
echo 远程控制系统 - 安装依赖
echo ============================================================
echo.

echo 正在检查Python版本...
python --version
if errorlevel 1 (
    echo 错误: 未找到Python，请先安装Python 3.7或更高版本
    pause
    exit /b 1
)

echo.
echo 正在安装依赖包...
echo.

pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo 安装失败，请检查网络连接或手动安装:
    echo pip install PyQt5 Pillow
    pause
    exit /b 1
)

echo.
echo ============================================================
echo 安装完成!
echo ============================================================
echo.
echo 使用说明:
echo 1. 服务器端: 运行 start_server.bat
echo 2. 被控端:   运行 start_agent.bat
echo 3. 控制端:   运行 start_controller.bat
echo.
echo 详细说明请查看 README.md
echo ============================================================
pause

