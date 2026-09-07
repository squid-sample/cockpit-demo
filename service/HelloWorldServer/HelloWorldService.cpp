#include <iostream>
#include <thread>
#include <chrono>
#include <atomic>
#include <signal.h>
#include <CommonAPI/CommonAPI.hpp>
#include "HelloWorldServerImpl.h"
#include <v1/demo/MyTypes.hpp>

std::atomic<bool> g_running(true);

void handleSignal(int signal) {
    std::cout << "[Server] Received signal " << signal << ", shutting down..." << std::endl;
    g_running.store(false);
}

void simulatePowerStateChanges(std::shared_ptr<HelloWorldServerImpl> service) {
    using namespace v1::demo;
    
    std::this_thread::sleep_for(std::chrono::seconds(5));
    service->setPowerState(MyTypes::PowerState::STR);
    
    std::this_thread::sleep_for(std::chrono::seconds(5));
    service->setPowerState(MyTypes::PowerState::ACTIVE);
    
    std::this_thread::sleep_for(std::chrono::seconds(5));
    service->setPowerState(MyTypes::PowerState::STR);
    
    std::this_thread::sleep_for(std::chrono::seconds(5));
    service->setPowerState(MyTypes::PowerState::OFF);
}

int main()
{
    std::cout << "[Server] Starting HelloWorldService..." << std::endl;

    signal(SIGINT, handleSignal);
    signal(SIGTERM, handleSignal);

    auto runtime = CommonAPI::Runtime::get();
    auto service = std::make_shared<HelloWorldServerImpl>();
    
    bool isRegistered = runtime->registerService("local", "demo.HelloWorld", service);
    std::cout << "[Server] Service registered: " << (isRegistered ? "success" : "failed") << std::endl;

    std::thread simulationThread(simulatePowerStateChanges, service);

    std::cout << "[Server] Service is running. Press Ctrl+C to stop." << std::endl;

    while (g_running.load()) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }

    // std::cout << "[Server] Unregistering service..." << std::endl;
    // runtime->unregisterService("local", "demo.HelloWorld");

    if (simulationThread.joinable()) {
        simulationThread.join();
    }

    std::cout << "[Server] HelloWorldService stopped." << std::endl;
    return 0;
}