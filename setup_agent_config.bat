@echo off
chcp 65001 >nul
echo ========================================
echo 远程控制系统 - 配置被控端
echo ========================================
echo.

set /p server_ip=请输入服务器IP地址:
set /p server_port=请输入服务器端口 (默认 5000):
set /p custom_name=请输入自定义主机名:

if "%server_port%"=="" set server_port=5000

echo.
echo 正在创建配置文件...

(
echo [Server]
echo ip = %server_ip%
echo port = %server_port%
echo.
echo [Agent]
echo name = %custom_name%
) > agent_config.ini

echo.
echo [成功] 配置文件已创建: agent_config.ini
echo.
echo 下一步操作:
echo 1. 测试连接: python agent.py --config agent_config.ini
echo 2. 静默模式: python agent.py --config agent_config.ini --silent
echo 3. 打包程序: 666.bat
echo 4. 设置自启: 设置开机自启.bat
echo.
pause
