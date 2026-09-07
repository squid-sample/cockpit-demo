@echo off
REM ============================================================
REM  QNX x86_64 交叉编译脚本
REM  构建 FaultCollector 及其依赖 (liblog)
REM  参照 D:\fdbus\build_qnx_x86_64 的构建方式
REM
REM  前置条件:
REM    1. QNX SDP 已安装 (D:/QNX_SDP/)
REM    2. QNX_HOST / QNX_TARGET 环境变量已设置 (运行 qnxsdp-env.bat)
REM    3. D:\fdbus\build_qnx_x86_64\lib\libfdbus.so 已编译好
REM    4. CMake 已安装 (D:/cmake/bin/cmake.exe)
REM ============================================================

setlocal enabledelayedexpansion

REM 检查 QNX 环境
if "%QNX_HOST%"=="" (
    echo [ERROR] QNX_HOST is not set. Please run qnxsdp-env.bat first.
    exit /b 1
)
if "%QNX_TARGET%"=="" (
    echo [ERROR] QNX_TARGET is not set. Please run qnxsdp-env.bat first.
    exit /b 1
)

REM 检查 fdbus QNX 库
if not exist "D:\fdbus\build_qnx_x86_64\lib\libfdbus.so" (
    echo [ERROR] D:\fdbus\build_qnx_x86_64\lib\libfdbus.so not found.
    echo Please build fdbus for QNX x86_64 first.
    exit /b 1
)

set TOOLCHAIN=D:/demo/tools/fdbus/fdbus/cmake/toolchain-qnx-x86_64.cmake
set GENERATOR=Unix Makefiles
set BUILD_TYPE=Release
set CMAKE=D:/cmake/bin/cmake.exe

echo ============================================================
echo  Step 1: Build liblog (QNX x86_64)
echo ============================================================

set LIBLOG_SRC=D:/demo/service/liblog
set LIBLOG_BUILD=%LIBLOG_SRC%/build_qnx_x86_64

echo Cleaning previous build...
if exist "%LIBLOG_BUILD%" rmdir /s /q "%LIBLOG_BUILD%"
mkdir "%LIBLOG_BUILD%"

echo Configuring liblog...
cd /d "%LIBLOG_BUILD%"
"%CMAKE%" -G "%GENERATOR%" ^
    -DCMAKE_TOOLCHAIN_FILE="%TOOLCHAIN%" ^
    -DCMAKE_BUILD_TYPE="%BUILD_TYPE%" ^
    "%LIBLOG_SRC%"
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] liblog cmake configure failed!
    exit /b 1
)

echo Building liblog...
"%CMAKE%" --build .
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] liblog build failed!
    exit /b 1
)

REM Verify liblog output
if not exist "%LIBLOG_BUILD%/liblogservice.so" (
    echo [WARNING] liblogservice.so not found in build directory.
    echo Files in build dir:
    dir "%LIBLOG_BUILD%" /b
)

echo ============================================================
echo  Step 2: Build FaultCollector (QNX x86_64)
echo ============================================================

set FC_SRC=D:/demo/service/FaultCollector
set FC_BUILD=%FC_SRC%/build_qnx_x86_64

echo Cleaning previous build...
if exist "%FC_BUILD%" rmdir /s /q "%FC_BUILD%"
mkdir "%FC_BUILD%"

echo Configuring FaultCollector...
cd /d "%FC_BUILD%"
"%CMAKE%" -G "%GENERATOR%" ^
    -DCMAKE_TOOLCHAIN_FILE="%TOOLCHAIN%" ^
    -DCMAKE_BUILD_TYPE="%BUILD_TYPE%" ^
    "%FC_SRC%"
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] FaultCollector cmake configure failed!
    exit /b 1
)

echo Building FaultCollector...
"%CMAKE%" --build .
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] FaultCollector build failed!
    exit /b 1
)

echo ============================================================
echo  Build completed successfully!
echo ============================================================
echo.
echo  Outputs:
echo    liblog:       %LIBLOG_BUILD%/liblogservice.so
echo    FaultCollector: %FC_BUILD%/faultcollector
echo    FaultReport:    %FC_BUILD%/libfaultreport.so
echo    Install dir:    D:/demo/dist/fault_qnx/
echo.
echo  To install, run:
echo    cd "%FC_BUILD%" ^&^& "%CMAKE%" --build . --target install
echo.

endlocal
