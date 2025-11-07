@echo off
chcp 65001 >nul
echo ========================================
echo 远程控制系统 - 设置开机自启 v2
echo ========================================
echo.

REM Check if running as administrator
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [警告] 未以管理员身份运行！
    echo 某些方式可能需要管理员权限。
    echo.
)

echo 请选择自启动方式:
echo 1. 任务计划程序 (推荐)
echo 2. 注册表运行键
echo 3. 启动文件夹
echo 4. 移除所有自启动
echo.

set /p choice=请输入选择 (1-4):

if "%choice%"=="1" goto method1
if "%choice%"=="2" goto method2
if "%choice%"=="3" goto method3
if "%choice%"=="4" goto method4
echo 无效的选择！
pause
exit /b 1

:method1
echo.
echo [方式 1] 任务计划程序设置
echo ========================================
echo.

REM Check for config file
if not exist "%~dp0agent_config.ini" (
    echo 错误: 未找到 agent_config.ini！
    echo 请先运行 配置被控端.bat
    pause
    exit /b 1
)

REM Check for exe file
set "AGENT_EXE=%~dp0release\RemoteAgent.exe"
if not exist "%AGENT_EXE%" (
    set "AGENT_EXE=%~dp0RemoteAgent.exe"
)
if not exist "%AGENT_EXE%" (
    echo 错误: 未找到 RemoteAgent.exe！
    echo 请先运行 666.bat 进行打包
    pause
    exit /b 1
)

set "CONFIG_FILE=%~dp0agent_config.ini"
set "TASK_NAME=RemoteControlAgent"

echo 正在创建计划任务...
echo 任务名称: %TASK_NAME%
echo 程序路径: %AGENT_EXE%
echo 配置文件: %CONFIG_FILE%
echo.

REM Delete existing task if any
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

REM Create new task
set "TASK_CMD=%AGENT_EXE% --config %CONFIG_FILE% --silent"
schtasks /create /tn "%TASK_NAME%" /tr "%TASK_CMD%" /sc onlogon /rl highest /f

if %errorLevel% equ 0 (
    echo.
    echo [成功] 任务创建成功！
    echo.
    echo 任务详情:
    echo   名称: %TASK_NAME%
    echo   触发器: 用户登录时
    echo   权限: 最高权限 (管理员)
    echo.
    echo 被控端将在您登录时自动启动。
) else (
    echo.
    echo [错误] 创建任务失败！
    echo 请确保以管理员身份运行此脚本。
)
goto end

:method2
echo.
echo [方式 2] 注册表运行键设置
echo ========================================
echo.

REM Check for config file
if not exist "%~dp0agent_config.ini" (
    echo 错误: 未找到 agent_config.ini！
    echo 请先运行 配置被控端.bat
    pause
    exit /b 1
)

REM Check for exe file
set "AGENT_EXE=%~dp0release\RemoteAgent.exe"
if not exist "%AGENT_EXE%" (
    set "AGENT_EXE=%~dp0RemoteAgent.exe"
)
if not exist "%AGENT_EXE%" (
    echo 错误: 未找到 RemoteAgent.exe！
    echo 请先运行 666.bat 进行打包
    pause
    exit /b 1
)

set "CONFIG_FILE=%~dp0agent_config.ini"
set "REG_NAME=RemoteControlAgent"

echo 正在添加注册表项...
echo 位置: HKCU\Software\Microsoft\Windows\CurrentVersion\Run
echo 名称: %REG_NAME%
echo.

set "REG_CMD=%AGENT_EXE% --config %CONFIG_FILE% --silent"
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "%REG_NAME%" /t REG_SZ /d "%REG_CMD%" /f

if %errorLevel% equ 0 (
    echo.
    echo [成功] 注册表项添加成功！
    echo.
    echo 被控端将在您登录时自动启动。
) else (
    echo.
    echo [错误] 添加注册表项失败！
)
goto end

:method3
echo.
echo [方式 3] 启动文件夹设置
echo ========================================
echo.

REM Check for config file
if not exist "%~dp0agent_config.ini" (
    echo 错误: 未找到 agent_config.ini！
    echo 请先运行 配置被控端.bat
    pause
    exit /b 1
)

REM Check for exe file
set "AGENT_EXE=%~dp0release\RemoteAgent.exe"
if not exist "%AGENT_EXE%" (
    set "AGENT_EXE=%~dp0RemoteAgent.exe"
)
if not exist "%AGENT_EXE%" (
    echo 错误: 未找到 RemoteAgent.exe！
    echo 请先运行 666.bat 进行打包
    pause
    exit /b 1
)

set "CONFIG_FILE=%~dp0agent_config.ini"
set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "STARTUP_BAT=%STARTUP_FOLDER%\RemoteAgent.bat"

echo 正在创建启动脚本...
echo 位置: %STARTUP_BAT%
echo.

(
echo @echo off
echo start "" "%AGENT_EXE%" --config "%CONFIG_FILE%" --silent
) > "%STARTUP_BAT%"

if exist "%STARTUP_BAT%" (
    echo.
    echo [成功] 启动脚本创建成功！
    echo.
    echo 被控端将在您登录时自动启动。
) else (
    echo.
    echo [错误] 创建启动脚本失败！
)
goto end

:method4
echo.
echo [方式 4] 移除所有自启动设置
echo ========================================
echo.

set "removed=0"

echo 正在检查任务计划程序...
schtasks /query /tn "RemoteControlAgent" >nul 2>&1
if %errorLevel% equ 0 (
    schtasks /delete /tn "RemoteControlAgent" /f >nul 2>&1
    if %errorLevel% equ 0 (
        echo [成功] 计划任务已移除
        set "removed=1"
    )
) else (
    echo [-] 未找到计划任务
)

echo.
echo 正在检查注册表运行键...
reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "RemoteControlAgent" >nul 2>&1
if %errorLevel% equ 0 (
    reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "RemoteControlAgent" /f >nul 2>&1
    if %errorLevel% equ 0 (
        echo [成功] 注册表项已移除
        set "removed=1"
    )
) else (
    echo [-] 未找到注册表项
)

echo.
echo 正在检查启动文件夹...
set "STARTUP_BAT=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\RemoteAgent.bat"
if exist "%STARTUP_BAT%" (
    del "%STARTUP_BAT%" >nul 2>&1
    if not exist "%STARTUP_BAT%" (
        echo [成功] 启动脚本已移除
        set "removed=1"
    )
) else (
    echo [-] 未找到启动脚本
)

echo.
if "%removed%"=="1" (
    echo [成功] 自启动设置已移除！
) else (
    echo [信息] 未找到任何自启动设置。
)
goto end

:end
echo.
echo ========================================
echo 操作完成！
echo ========================================
echo.
pause

