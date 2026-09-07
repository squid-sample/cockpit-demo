cmake_minimum_required(VERSION 3.10)
project(FaultCollector)

set(CMAKE_CXX_STANDARD 11)
if(CMAKE_SYSTEM_NAME STREQUAL "QNX")
    # Preserve toolchain flags (e.g. -Vgcc_ntox86_64) and append our own
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -g -Wall")
else()
    set(CMAKE_CXX_FLAGS "-g -Wall -std=c++11")
endif()

include_directories(include
    ../..
    ../../tools/fdbus/fdbus/public
    ../liblog/include
)

if(CMAKE_SYSTEM_NAME STREQUAL "QNX")
    # QNX x86_64 cross-compilation: use D:\fdbus prebuilt fdbus lib
    set(CMAKE_INSTALL_PREFIX "D:/demo/dist/fault_qnx" CACHE PATH "Install DIR" FORCE)
    link_directories(D:/fdbus/build_qnx_x86_64/lib
        ../liblog/build_qnx_x86_64
    )
else()
    # MinGW / native build
    set(CMAKE_INSTALL_PREFIX "D:/demo/dist/fault" CACHE PATH "Install DIR" FORCE)
    link_directories(../../tools/fdbus/build_mingw
        ../liblog/build
    )
endif()

add_library(faultreport SHARED
    src/FaultReport.cpp
)

add_executable(faultcollector
    src/main.cpp
    src/FaultCollectorManager.cpp
    src/FaultCollector.cpp
    src/FdbusAdapter.cpp
    src/FaultCache.cpp
    src/FaultStorage.cpp
)

if(MINGW)
    target_link_libraries(faultcollector fdbus logservice ws2_32 iphlpapi)
    target_link_libraries(faultreport ws2_32)
elseif(CMAKE_SYSTEM_NAME STREQUAL "QNX")
    target_link_libraries(faultcollector fdbus logservice ham pthread)
    target_link_libraries(faultreport)
else()
    target_link_libraries(faultcollector fdbus logservice ham pthread)
    target_link_libraries(faultreport)
endif()

install(TARGETS faultcollector RUNTIME DESTINATION .)
install(TARGETS faultreport LIBRARY DESTINATION .)
install(FILES include/FaultCommon.h include/FaultReport.h 
              include/FaultCollectorManager.h include/Singleton.h
        DESTINATION include)