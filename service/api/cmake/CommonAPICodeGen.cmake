# CommonAPICodeGen.cmake
# 封装 CommonAPI FIDL + SOME/IP 代码生成 & 库编译工具函数

# if(__COMMONAPI_CODEGEN_CMAKE__)
#     return()
# endif()
# set(__COMMONAPI_CODEGEN_CMAKE__ ON)

# # ===================== 1. 查找生成器工具 =====================
# find_program(COMMONAPI_CORE_GEN
#     NAMES commonapi-core-generator-linux-x86_64 commonapi-core-generator.exe
#     DOC "CommonAPI Core IDL 代码生成器"
# )
# find_program(COMMONAPI_SOMEIP_GEN
#     NAMES commonapi-someip-generator-linux-x86_64 commonapi-someip-generator.exe
#     DOC "CommonAPI SOME/IP 绑定代码生成器"
# )

# if(NOT COMMONAPI_CORE_GEN OR NOT COMMONAPI_SOMEIP_GEN)
#     message(FATAL_ERROR "缺少 CommonAPI 代码生成器，请配置工具路径！")
# endif()

# ===================== 2. 核心函数：generate_commonapi_someip_lib =====================
# 参数说明：
# TARGET_NAME        输出库名
# FIDL_FILE          主fidl文件完整路径
# FDEPL_FILE         对应fdepl部署文件完整路径
# GEN_OUTPUT_DIR    生成代码输出目录
# LIB_TYPE           STATIC / SHARED 库类型
function(generate_commonapi_someip_lib
    TARGET_NAME
    FIDL_FILE
    FDEPL_FILE
    GEN_OUTPUT_DIR
    LIB_TYPE
)
    # 校验入参
    if(NOT EXISTS ${FIDL_FILE})
        message(FATAL_ERROR "FIDL 文件不存在: ${FIDL_FILE}")
    endif()
    if(NOT EXISTS ${FDEPL_FILE})
        message(FATAL_ERROR "FDEPL 文件不存在: ${FDEPL_FILE}")
    endif()

    # 定义生成目录
    set(GEN_DIR ${GEN_OUTPUT_DIR})
    file(MAKE_DIRECTORY ${GEN_DIR})

    # 收集生成后的源文件（cpp/hpp）
    file(GLOB_RECURSE GEN_SRC_LIST
        ${GEN_DIR}/*.cpp
        ${GEN_DIR}/*.hpp
    )

    # 添加自定义命令：代码生成（构建前自动执行）
    add_custom_command(
        OUTPUT ${GEN_SRC_LIST}
        # 前置操作：清空旧生成文件
        COMMAND ${CMAKE_COMMAND} -E rm -rf ${GEN_DIR}
        COMMAND ${CMAKE_COMMAND} -E make_directory ${GEN_DIR}
        # 1. 生成 Core 基础代码
        COMMAND ${COMMONAPI_CORE_GEN} -d ${GEN_DIR} -sk ${FIDL_FILE}
        # 2. 生成 SOME/IP 绑定代码
        COMMAND ${COMMONAPI_SOMEIP_GEN} -d ${GEN_DIR} ${FDEPL_FILE}
        # 依赖：fidl/fdepl 修改则重新生成
        DEPENDS ${FIDL_FILE} ${FDEPL_FILE}
        COMMENT "===== Generate CommonAPI SOME/IP code to ${GEN_DIR} ====="
        VERBATIM
    )

    # 封装生成代码为目标，保证编译顺序
    add_custom_target(${TARGET_NAME}_gen
        DEPENDS ${GEN_SRC_LIST}
    )

    # 编译静态/动态库
    add_library(${TARGET_NAME} ${LIB_TYPE} ${GEN_SRC_LIST})
    # 强制先生成代码再编译库
    add_dependencies(${TARGET_NAME} ${TARGET_NAME}_gen)

    # 头文件目录导出（供上层工程include）
    target_include_directories(${TARGET_NAME}
        PUBLIC
            ${GEN_DIR}
    )

    # 链接依赖 CommonAPI + vsomeip3
    find_package(CommonAPI REQUIRED CONFIG)
    find_package(CommonAPI-SomeIP REQUIRED CONFIG)
    find_package(vsomeip3 REQUIRED CONFIG)

    target_link_libraries(${TARGET_NAME}
        PUBLIC
            CommonAPI
            CommonAPI-SomeIP
            vsomeip3
    )

    # 安装规则
    install(TARGETS ${TARGET_NAME}
        ARCHIVE DESTINATION lib
        LIBRARY DESTINATION lib
        RUNTIME DESTINATION bin
    )

    # 安装生成头文件
    file(GLOB GEN_HEADERS ${GEN_DIR}/*.hpp)
    install(FILES ${GEN_HEADERS} DESTINATION include)
endfunction()