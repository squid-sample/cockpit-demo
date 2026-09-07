cmake_minimum_required(VERSION 3.10)
project(PowerManagerService)

if(CMAKE_SYSTEM_NAME STREQUAL "QNX")
    set(CMAKE_CXX_STANDARD 14)
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -g -Wall")
else()
    set(CMAKE_CXX_STANDARD 11)
    set(CMAKE_CXX_FLAGS "-g -Wall -std=c++11")
endif()

include_directories(include
    ../..
    ../../tools/fdbus/fdbus/public
    ../liblog/include
)

if(CMAKE_SYSTEM_NAME STREQUAL "QNX")
    set(CMAKE_INSTALL_PREFIX "D:/demo/dist/power_qnx" CACHE PATH "Install DIR" FORCE)
    link_directories(D:/fdbus/build_qnx_x86_64/lib
        ../liblog/build_qnx_x86_64
    )
else()
    set(CMAKE_INSTALL_PREFIX "D:/demo/dist/power" CACHE PATH "Install DIR" FORCE)
    link_directories(../../tools/fdbus/build_mingw
        ../liblog/build
    )
endif()

add_executable(powermanager
    src/main.cpp
    src/PowerManager.cpp
    src/EcdClient.cpp
    src/FdbusPowerAdapter.cpp
    src/KeyEventHandler.cpp
    src/StrNotifier.cpp
)

if(MINGW)
    target_link_libraries(powermanager fdbus logservice ws2_32 iphlpapi)
elseif(CMAKE_SYSTEM_NAME STREQUAL "QNX")
    target_link_libraries(powermanager fdbus logservice c++)
else()
    target_link_libraries(powermanager fdbus logservice pthread)
endif()

install(TARGETS powermanager RUNTIME DESTINATION .)
install(FILES include/PowerManagerCommon.h
              include/EcdClient.h
              include/PowerManager.h
              include/FdbusPowerAdapter.h
              include/KeyEventHandler.h
              include/StrNotifier.h
              include/Singleton.h
        DESTINATION include)
