@echo off
chcp 65001 >nul
echo ========================================
echo 远程控制系统 - 设置开机自启
echo ========================================
echo.

echo 请选择自启动方式:
echo 1. 任务计划程序 (推荐，支持管理员权限)
echo 2. 注册表运行键 (简单，无需管理员权限)
echo 3. 启动文件夹 (最简单)
echo 4. 移除所有自启动设置
echo.

set /p choice=请输入选择 (1-4):

if "%choice%"=="1" goto task_scheduler
if "%choice%"=="2" goto registry
if "%choice%"=="3" goto startup_folder
if "%choice%"=="4" goto remove_all
echo 无效的选择！
pause
exit /b 1

:task_scheduler
echo.
echo [方式 1] 设置任务计划程序...
echo.

REM Check if config file exists
if exist "%~dp0agent_config.ini" (
    echo 发现已有配置文件: agent_config.ini
    set /p use_existing=是否使用现有配置? (Y/N):
    if /i "%use_existing%"=="Y" goto use_config_task
)

echo.
echo 请配置服务器连接信息:
set /p server_ip=服务器IP地址:
set /p server_port=服务器端口 (默认 5000):
set /p custom_name=自定义主机名:

if "%server_port%"=="" set server_port=5000

REM Create config file
(
echo [Server]
echo ip = %server_ip%
echo port = %server_port%
echo.
echo [Agent]
echo name = %custom_name%
) > "%~dp0agent_config.ini"

:use_config_task
set exe_path=%~dp0release\RemoteAgent.exe
set config_path=%~dp0agent_config.ini

if not exist "%exe_path%" (
    echo 错误: 未找到 RemoteAgent.exe
    echo 请先运行 666.bat 进行打包
    pause
    exit /b 1
)

echo.
echo 正在创建计划任务...
schtasks /create /tn "RemoteControlAgent" /tr "\"%exe_path%\" --config \"%config_path%\" --silent" /sc onlogon /rl highest /f >nul 2>&1

if errorlevel 1 (
    echo 创建任务失败！
    pause
    exit /b 1
)

echo.
echo [成功] 计划任务创建成功！
echo   任务名称: RemoteControlAgent
echo   触发器: 用户登录时
echo   权限: 最高权限
goto end

:registry
echo.
echo [方式 2] 设置注册表运行键...
echo.

REM Check if config file exists
if exist "%~dp0agent_config.ini" (
    echo 发现已有配置文件: agent_config.ini
    set /p use_existing=是否使用现有配置? (Y/N):
    if /i "%use_existing%"=="Y" goto use_config_reg
)

echo.
echo 请配置服务器连接信息:
set /p server_ip=服务器IP地址:
set /p server_port=服务器端口 (默认 5000):
set /p custom_name=自定义主机名:

if "%server_port%"=="" set server_port=5000

REM Create config file
(
echo [Server]
echo ip = %server_ip%
echo port = %server_port%
echo.
echo [Agent]
echo name = %custom_name%
) > "%~dp0agent_config.ini"

:use_config_reg
set exe_path=%~dp0release\RemoteAgent.exe
set config_path=%~dp0agent_config.ini

if not exist "%exe_path%" (
    echo 错误: 未找到 RemoteAgent.exe
    echo 请先运行 666.bat 进行打包
    pause
    exit /b 1
)

echo.
echo 正在添加注册表项...
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "RemoteControlAgent" /t REG_SZ /d "\"%exe_path%\" --config \"%config_path%\" --silent" /f

if errorlevel 1 (
    echo 添加注册表项失败！
    pause
    exit /b 1
)

echo.
echo [成功] 注册表项添加成功！
echo   位置: HKCU\Software\Microsoft\Windows\CurrentVersion\Run
echo   名称: RemoteControlAgent
goto end

:startup_folder
echo.
echo [方式 3] 设置启动文件夹...
echo.

REM Check if config file exists
if exist "%~dp0agent_config.ini" (
    echo 发现已有配置文件: agent_config.ini
    set /p use_existing=是否使用现有配置? (Y/N):
    if /i "%use_existing%"=="Y" goto use_config_startup
)

echo.
echo 请配置服务器连接信息:
set /p server_ip=服务器IP地址:
set /p server_port=服务器端口 (默认 5000):
set /p custom_name=自定义主机名:

if "%server_port%"=="" set server_port=5000

REM Create config file
(
echo [Server]
echo ip = %server_ip%
echo port = %server_port%
echo.
echo [Agent]
echo name = %custom_name%
) > "%~dp0agent_config.ini"

:use_config_startup
set exe_path=%~dp0release\RemoteAgent.exe
set config_path=%~dp0agent_config.ini

if not exist "%exe_path%" (
    echo 错误: 未找到 RemoteAgent.exe
    echo 请先运行 666.bat 进行打包
    pause
    exit /b 1
)

set startup_folder=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup

echo.
echo 正在创建启动脚本...
echo @echo off > "%startup_folder%\RemoteAgent.bat"
echo start "" "%exe_path%" --config "%config_path%" --silent >> "%startup_folder%\RemoteAgent.bat"

echo.
echo [成功] 启动脚本创建成功！
echo   位置: %startup_folder%\RemoteAgent.bat
goto end

:remove_all
echo.
echo [方式 4] 移除所有自启动设置...
echo.

echo 正在删除计划任务...
schtasks /delete /tn "RemoteControlAgent" /f 2>nul
if errorlevel 1 (
    echo - 未找到任务或删除失败
) else (
    echo [成功] 计划任务已删除
)

echo.
echo 正在删除注册表项...
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "RemoteControlAgent" /f 2>nul
if errorlevel 1 (
    echo - 未找到注册表项或删除失败
) else (
    echo [成功] 注册表项已删除
)

echo.
echo 正在删除启动脚本...
set startup_folder=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
del "%startup_folder%\RemoteAgent.bat" 2>nul
if errorlevel 1 (
    echo - 未找到启动脚本或删除失败
) else (
    echo [成功] 启动脚本已删除
)

echo.
echo [成功] 所有自启动设置已移除！
goto end

:end
echo.
echo ========================================
echo 操作完成！
echo ========================================
pause
