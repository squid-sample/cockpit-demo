cmake_minimum_required(VERSION 3.10)
project(LogServer)

set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_FLAGS "-g -Wall")
set(CMAKE_INSTALL_PREFIX "D:/demo/dist/data" CACHE PATH "Install DIR" FORCE)

set(CMAKE_PREFIX_PATH "D:/demo/tools/vsomeip/vsomeip/build"
    "D:/demo/tools/capicxx-core-runtime/capicxx-core-runtime/build"
    "D:/demo/tools/capicxx-someip-runtime/capicxx-someip-runtime/build"
    CACHE PATH "")
FIND_PACKAGE(CommonAPI 3.2.0 REQUIRED CONFIG NO_SYSTEM_ENVIRONMENT_PATH NO_CMAKE_SYSTEM_PATH)
FIND_PACKAGE(CommonAPI-SomeIP 3.2.0 REQUIRED CONFIG NO_SYSTEM_ENVIRONMENT_PATH NO_CMAKE_SYSTEM_PATH)
find_package (vsomeip3 3.7.3 REQUIRED CONFIG NO_SYSTEM_ENVIRONMENT_PATH NO_CMAKE_SYSTEM_PATH)

include_directories(../../dist/api-gen
    ${COMMONAPI_INCLUDE_DIRS}
    ${COMMONAPI_SOMEIP_INCLUDE_DIRS}
    ${VSOMEIP3_INCLUDE_DIRS}
)

link_directories(../../dist/data)

add_executable(logserver LogServerService.cpp
    LogServerImpl.cpp
    LogManager.cpp
    LogConfig.cpp
    LogSource.cpp
    LogWriter.cpp
    LogReader.cpp
    LogExporter.cpp
    UsbMonitor.cpp)

target_link_libraries(logserver LogServerDemo-SomeIP CommonAPI CommonAPI-SomeIP vsomeip3)

install(TARGETS logserver RUNTIME DESTINATION .)