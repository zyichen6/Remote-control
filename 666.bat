@echo off
chcp 65001 >nul
echo ========================================
echo 远程控制系统 - 打包所有程序
echo ========================================
echo.

echo [1/4] 检查PyInstaller...
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo PyInstaller未安装，正在安装...
    pip install pyinstaller
) else (
    echo PyInstaller已安装
)
echo.

echo [2/4] 打包服务器端...
cd build_spec
pyinstaller --clean server.spec
if errorlevel 1 (
    echo 服务器端打包失败！
    pause
    exit /b 1
)
echo 服务器端打包完成！
echo.

echo [3/4] 打包被控端...
pyinstaller --clean agent.spec
if errorlevel 1 (
    echo 被控端打包失败！
    pause
    exit /b 1
)
echo 被控端打包完成！
echo.

echo [4/4] 打包控制端...
pyinstaller --clean controller.spec
if errorlevel 1 (
    echo 控制端打包失败！
    pause
    exit /b 1
)
echo 控制端打包完成！
cd ..
echo.

echo ========================================
echo 打包完成！
echo ========================================
echo.
echo 生成的文件位置：
echo - 服务器端: build_spec\dist\RemoteServer.exe
echo - 被控端:   build_spec\dist\RemoteAgent.exe
echo - 控制端:   build_spec\dist\RemoteController.exe
echo.

echo 正在复制到发布目录...
if not exist "release" mkdir release
copy /Y build_spec\dist\RemoteServer.exe release\
copy /Y build_spec\dist\RemoteAgent.exe release\
copy /Y build_spec\dist\RemoteController.exe release\

echo.
echo 所有程序已复制到 release 目录！
echo.
pause

