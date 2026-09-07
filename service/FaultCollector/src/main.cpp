#define LOG_TAG "FaultCollector"
#include "log.h"

#include "FaultCollectorManager.h"
#include <signal.h>

void normal_exit_handler(int sig) {
    (void)sig;
    LOG_INFO("received normal exit signal: %d", sig);
    FaultCollectorManager* manager = Singleton<FaultCollectorManager>::instance();
    if (manager) {
        manager->markNormalExit();
        manager->stop();
    }
}

void crash_handler(int sig) {
    (void)sig;
    LOG_FATAL("received crash signal: %d", sig);
    FaultCollectorManager* manager = Singleton<FaultCollectorManager>::instance();
    if (manager) {
        manager->stop();
    }
    exit(-1);
}

int main(int argc, char* argv[]) {
    (void)argc;
    (void)argv;

    log_init("log");

    LOG_INFO("FaultCollector starting...");

    signal(SIGTERM, normal_exit_handler);
    signal(SIGINT, normal_exit_handler);
    signal(SIGSEGV, crash_handler);
    signal(SIGABRT, crash_handler);
    signal(SIGILL, crash_handler);
    signal(SIGFPE, crash_handler);

    FaultCollectorManager* manager = Singleton<FaultCollectorManager>::instance();
    if (!manager || !manager->init()) {
        LOG_ERROR("Failed to initialize FaultCollectorManager");
        return -1;
    }

    LOG_INFO("FaultCollector running");
    manager->run();

    LOG_INFO("FaultCollector exited");
    return 0;
}
