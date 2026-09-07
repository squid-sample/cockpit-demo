cmake_minimum_required(VERSION 3.10)
project(LogService)

set(CMAKE_CXX_STANDARD 14)
if(CMAKE_SYSTEM_NAME STREQUAL "QNX")
    # Preserve toolchain flags (e.g. -Vgcc_ntox86_64) and append our own
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -g -Wall")
else()
    set(CMAKE_CXX_FLAGS "-g -Wall -std=c++14")
endif()

include_directories(include
    ../..
    ../../tools/fdbus/fdbus/public
)

if(CMAKE_SYSTEM_NAME STREQUAL "QNX")
    # QNX x86_64 cross-compilation
    set(CMAKE_INSTALL_PREFIX "D:/demo/dist/log_qnx" CACHE PATH "Install DIR" FORCE)
    # liblog doesn't link fdbus, but keep the path for compatibility
    link_directories(D:/fdbus/build_qnx_x86_64/lib)
else()
    set(CMAKE_INSTALL_PREFIX "D:/demo/dist/log" CACHE PATH "Install DIR" FORCE)
    link_directories(../../tools/fdbus/build_mingw)
endif()

add_library(logservice SHARED
    src/LogManager.cpp
    src/LogWriter.cpp
    src/LogConsoleAdapter.cpp
    src/LogFileWriter.cpp
    src/LogCommon.cpp
    src/LogSlog2Writer.cpp
)

add_executable(logservice_demo
    src/main.cpp
)

if(MINGW)
    target_link_libraries(logservice ws2_32)
    target_link_libraries(logservice_demo logservice)
else()
    target_link_libraries(logservice slog2 pthread)
    target_link_libraries(logservice_demo logservice)
endif()

install(TARGETS logservice LIBRARY DESTINATION .)
install(FILES include/log.h include/LogCommon.h
        DESTINATION include)