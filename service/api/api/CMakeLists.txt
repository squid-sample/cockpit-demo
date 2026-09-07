cmake_minimum_required(VERSION 3.10)
project(HelloWorld-SOMIPLib)

set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_FLAGS "-g -Wall")
set(CMAKE_INSTALL_PREFIX "D:/demo/dist/data" CACHE PATH "Install DIR" FORCE)

set(BUILD_SHARED_LIBS ON CACHE BOOL "Build shared libraries")

set(CMAKE_PREFIX_PATH "D:/demo/tools/vsomeip/vsomeip/build"
    "D:/demo/tools/capicxx-core-runtime/capicxx-core-runtime/build"
    "D:/demo/tools/capicxx-someip-runtime/capicxx-someip-runtime/build"
    CACHE PATH "")
FIND_PACKAGE(CommonAPI 3.2.0 REQUIRED CONFIG NO_SYSTEM_ENVIRONMENT_PATH NO_CMAKE_SYSTEM_PATH)
FIND_PACKAGE(CommonAPI-SomeIP 3.2.0 REQUIRED CONFIG NO_SYSTEM_ENVIRONMENT_PATH NO_CMAKE_SYSTEM_PATH)
find_package (vsomeip3 3.7.3 REQUIRED CONFIG NO_SYSTEM_ENVIRONMENT_PATH NO_CMAKE_SYSTEM_PATH)

include_directories(../../../dist/api-gen
    ${COMMONAPI_INCLUDE_DIRS}
    ${COMMONAPI_SOMEIP_INCLUDE_DIRS}
    ${VSOMEIP3_INCLUDE_DIRS}
)

message(STATUS "CMAKE_INSTALL_PREFIX ${CMAKE_INSTALL_PREFIX}")

file(GLOB_RECURSE DEMO_GENERATED_SOURCES
    ../../../dist/api-gen/v1/demo/*.cpp
)

file(GLOB_RECURSE LOGSERVER_GENERATED_SOURCES
    ../../../dist/api-gen/v1/logserver/*.cpp
)

add_library(HelloWorldDemo-SomeIP SHARED
    ${DEMO_GENERATED_SOURCES}
)

target_link_libraries(HelloWorldDemo-SomeIP
    CommonAPI
    CommonAPI-SomeIP
    vsomeip3
)

add_library(LogServerDemo-SomeIP SHARED
    ${LOGSERVER_GENERATED_SOURCES}
)

target_link_libraries(LogServerDemo-SomeIP
    CommonAPI
    CommonAPI-SomeIP
    vsomeip3
)

install(TARGETS HelloWorldDemo-SomeIP LogServerDemo-SomeIP RUNTIME DESTINATION .)