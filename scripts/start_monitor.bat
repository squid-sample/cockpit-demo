@echo off
chcp 936 >nul
setlocal

rem ===== 路径（bat 与脚本在同一目录）=====
set "PYW=C:\msys64\ucrt64\bin\pythonw.exe"
set "APPDIR=%~dp0"

:menu
cls
echo ==========================================
echo            监听程序一键启动
echo ==========================================
echo.
echo    [1] 启动 加密货币监听
echo    [2] 启动 A股监听
echo    [3] 两个都启动
echo    [4] 弹出股票设置弹框
echo    [5] 退出
echo.
choice /c 12345 /n /m "请输入选项 1-5: "
if errorlevel 5 exit /b 0
if errorlevel 4 goto stock_settings
if errorlevel 3 goto both
if errorlevel 2 goto stock
if errorlevel 1 goto crypto

:crypto
start "" /D "%APPDIR%" "%PYW%" "%APPDIR%crypto_tracker.py"
goto started

:stock
start "" /D "%APPDIR%" "%PYW%" "%APPDIR%a_stock_realtime.py"
goto started

:both
start "" /D "%APPDIR%" "%PYW%" "%APPDIR%crypto_tracker.py"
start "" /D "%APPDIR%" "%PYW%" "%APPDIR%a_stock_realtime.py"
goto started

:stock_settings
start "" /D "%APPDIR%" "%PYW%" "%APPDIR%a_stock_realtime.py" --open-settings
goto started

:started
echo.
echo 启动指令已发出。若程序已在运行，会弹窗提示，不会重复启动。
echo [4] 弹出股票设置弹框：若监控已在运行则直接弹框，未运行则先启动再弹框。
ping 127.0.0.1 -n 5 >nul
exit /b 0