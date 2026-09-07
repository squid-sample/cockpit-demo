#define LOG_TAG "PowerManagerService"
#include "log.h"

#include "PowerManager.h"
#include "Singleton.h"
#include <signal.h>

static void on_exit_signal(int sig) {
    (void)sig;
    LOG_INFO("received exit signal: %d", sig);
    PowerManager* manager = Singleton<PowerManager>::instance();
    if (manager) {
        manager->stop();
    }
}

int main(int argc, char* argv[]) {
    (void)argc;
    (void)argv;

    log_init("log");

    LOG_INFO("PowerManagerService starting...");

    signal(SIGTERM, on_exit_signal);
    signal(SIGINT, on_exit_signal);

    PowerManager* manager = Singleton<PowerManager>::instance();
    if (!manager || !manager->init()) {
        LOG_ERROR("Failed to initialize PowerManager");
        return -1;
    }

    LOG_INFO("PowerManagerService running");
    manager->run();

    LOG_INFO("PowerManagerService exited");
    return 0;
}
