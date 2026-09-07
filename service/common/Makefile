# ========== 配置项 ==========
# 所有需要编译的服务目录名（自行增删）
SERVICES := \
	api \
	HelloWorldServer \
	HelloWorldClient
# 构建目录
MODULE_BUILD_DIR := build
# CMake 构建类型：Debug / Release
CMAKE_BUILD_TYPE ?= Release
# 编译线程数
MAKE_JOBS ?= $(shell nproc)

ROOT := $(CURDIR)/service

# ========== 伪目标 ==========
.PHONY: all clean rebuild $(SERVICES)

# 默认目标：编译所有服务
all: $(SERVICES)

# 逐个编译单个服务
# $(SERVICES):
# 	@mkdir -p $(ROOT)\$@/$(MODULE_BUILD_DIR)
# 	cd $(MODULE_BUILD_DIR)/$(ROOT)\$@ && cmake .. -G "MinGW Makefiles" -DCMAKE_CXX_COMPILER=g++ -DCMAKE_C_COMPILER=gcc
# 	cd $(MODULE_BUILD_DIR)/$(ROOT)\$@ && make -j$(MAKE_JOBS)

$(SERVICES):
	@if not exist "$(ROOT)\$@\$(MODULE_BUILD_DIR)" mkdir "$(ROOT)\$@\$(MODULE_BUILD_DIR)"
	cd "$(ROOT)\$@\$(MODULE_BUILD_DIR)" && cmake .. -G "MinGW Makefiles" -DCMAKE_CXX_COMPILER=g++ -DCMAKE_C_COMPILER=gcc $(CMAKE_FLAGS) ..
	cd "$(ROOT)\$@\$(MODULE_BUILD_DIR)" && mingw32-make
	cd "$(ROOT)\$@\$(MODULE_BUILD_DIR)" && mingw32-make install


# install: $(SERVICES)
# 	@for %%s in ($(SERVICES)) do ( \
# 		echo Installing %%s... & \
# 		cd %%s\$(MODULE_BUILD_DIR) & \
# 		mingw32-make install \
# 	)
clean:
	@for %%s in ($(SERVICES)) do ( \
		if exist %%s\$(MODULE_BUILD_DIR) rmdir /s /q %%s\$(MODULE_BUILD_DIR) \
	)

rebuild: clean all install