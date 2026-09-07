#define LOG_TAG "FaultCollector"
#include "log.h"

int main(int argc, char** argv) {
    log_init("log");

    LOG_TRACE("This is a trace message");
    LOG_DEBUG("This is a debug message");
    LOG_INFO("FaultCollector module initialized");
    LOG_WARN("Warning: low memory");
    LOG_ERROR("Error: connection failed");
    LOG_FATAL("Fatal: system crash");

    LOG_INFO("Hello %s, count=%d", "world", 123);

    log_set_global_level(LOG_LEVEL_WARN);

    LOG_INFO("This info message should NOT appear");
    LOG_WARN("This warning SHOULD appear");
    LOG_ERROR("This error SHOULD appear");

    log_set_global_level(LOG_LEVEL_INFO);
    LOG_INFO("Global level restored to INFO");

    log_set_module_level("TestModule", LOG_LEVEL_DEBUG);
    LOG_INFO("Testing module level configuration");

    return 0;
}
