#include <iostream>
#include <thread>
#include <chrono>
#include <atomic>
#include <signal.h>
#include <CommonAPI/CommonAPI.hpp>
#include "LogServerImpl.h"

std::atomic<bool> g_running(true);

void handleSignal(int signal) {
    std::cout << "[LogServer] Received signal " << signal << ", shutting down..." << std::endl;
    g_running.store(false);
}

int main()
{
    std::cout << "[LogServer] Starting LogServerService..." << std::endl;

    signal(SIGINT, handleSignal);
    signal(SIGTERM, handleSignal);

    auto service = std::make_shared<LogServerImpl>();
    
    if (!service->init()) {
        std::cerr << "[LogServer] Failed to initialize LogServer" << std::endl;
        return 1;
    }

    auto runtime = CommonAPI::Runtime::get();
    bool isRegistered = runtime->registerService("local", "logserver.LogServer", service);
    std::cout << "[LogServer] Service registered: " << (isRegistered ? "success" : "failed") << std::endl;

    if (!service->start()) {
        std::cerr << "[LogServer] Failed to start LogServer" << std::endl;
        return 1;
    }

    std::cout << "[LogServer] Service is running. Press Ctrl+C to stop." << std::endl;

    while (g_running.load()) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }

    service->stop();

    std::cout << "[LogServer] LogServerService stopped." << std::endl;
    return 0;
}