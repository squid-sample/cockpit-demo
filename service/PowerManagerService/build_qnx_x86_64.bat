@echo off
chcp 65001 >nul
REM ============================================================
REM  QNX x86_64 cross-compile script for PowerManagerService
REM  Mirrors D:\demo\build_qnx_x86_64.bat approach
REM
REM  Prerequisites:
REM    1. QNX SDP installed at D:\QNX_SDP
REM    2. D:\fdbus\build_qnx_x86_64\lib\libfdbus.so prebuilt
REM    3. liblog built at service\liblog\build_qnx_x86_64
REM    4. CMake in PATH
REM ============================================================

setlocal enabledelayedexpansion

REM Source QNX SDP environment
call D:\QNX_SDP\qnxsdp-env.bat

REM Check QNX environment
if "%QNX_HOST%"=="" (
    echo [ERROR] QNX_HOST is not set.
    exit /b 1
)
if "%QNX_TARGET%"=="" (
    echo [ERROR] QNX_TARGET is not set.
    exit /b 1
)

REM Check fdbus QNX library
if not exist "D:\fdbus\build_qnx_x86_64\lib\libfdbus.so" (
    echo [ERROR] D:\fdbus\build_qnx_x86_64\lib\libfdbus.so not found.
    exit /b 1
)

set TOOLCHAIN=D:/demo/tools/fdbus/fdbus/cmake/toolchain-qnx-x86_64.cmake
set GENERATOR=Unix Makefiles
set BUILD_TYPE=Release
set CMAKE=cmake

echo ============================================================
echo  Step 1: Build liblog (QNX x86_64)
echo ============================================================

set LIBLOG_SRC=D:/demo/service/liblog
set LIBLOG_BUILD=%LIBLOG_SRC%/build_qnx_x86_64

if exist "%LIBLOG_BUILD%\liblogservice.so" (
    echo liblog already built, skipping.
    goto build_pm
)

echo Cleaning previous build...
if exist "%LIBLOG_BUILD%" rmdir /s /q "%LIBLOG_BUILD%"
mkdir "%LIBLOG_BUILD%"

echo Configuring liblog...
pushd "%LIBLOG_BUILD%"
"%CMAKE%" -G "%GENERATOR%" ^
    -DCMAKE_TOOLCHAIN_FILE="%TOOLCHAIN%" ^
    -DCMAKE_BUILD_TYPE="%BUILD_TYPE%" ^
    "%LIBLOG_SRC%"
if %ERRORLEVEL% NEQ 0 (
    popd
    echo [ERROR] liblog cmake configure failed!
    exit /b 1
)

echo Building liblog...
"%CMAKE%" --build .
if %ERRORLEVEL% NEQ 0 (
    popd
    echo [ERROR] liblog build failed!
    exit /b 1
)
popd

if not exist "%LIBLOG_BUILD%\liblogservice.so" (
    echo [WARNING] liblogservice.so not found in build directory.
    dir "%LIBLOG_BUILD%" /b
)

:build_pm

echo ============================================================
echo  Step 2: Build PowerManagerService (QNX x86_64)
echo ============================================================

set PM_SRC=D:/demo/service/PowerManagerService
set PM_BUILD=%PM_SRC%/build_qnx_x86_64

echo Cleaning previous build...
if exist "%PM_BUILD%" rmdir /s /q "%PM_BUILD%"
mkdir "%PM_BUILD%"

echo Configuring PowerManagerService...
pushd "%PM_BUILD%"
"%CMAKE%" -G "%GENERATOR%" ^
    -DCMAKE_TOOLCHAIN_FILE="%TOOLCHAIN%" ^
    -DCMAKE_BUILD_TYPE="%BUILD_TYPE%" ^
    "%PM_SRC%"
if %ERRORLEVEL% NEQ 0 (
    popd
    echo [ERROR] PowerManagerService cmake configure failed!
    exit /b 1
)

echo Building PowerManagerService...
"%CMAKE%" --build .
if %ERRORLEVEL% NEQ 0 (
    popd
    echo [ERROR] PowerManagerService build failed!
    exit /b 1
)
popd

echo ============================================================
echo  Build completed successfully!
echo ============================================================
echo.
echo  Outputs:
echo    liblog:          %LIBLOG_BUILD%\liblogservice.so
echo    PowerManager:    %PM_BUILD%\powermanager
echo    Install dir:     D:/demo/dist/power_qnx/
echo.
echo  To install, run:
echo    cd "%PM_BUILD%" ^&^& "%CMAKE%" --build . --target install
echo.

endlocal
