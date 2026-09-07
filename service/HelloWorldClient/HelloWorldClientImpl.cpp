#include <iostream>
#include "HelloWorldClientImpl.h"
#include <CommonAPI/CommonAPI.hpp>
#include <thread>
#include <string>

HelloWorldClientImpl::HelloWorldClientImpl()
{
}

HelloWorldClientImpl::~HelloWorldClientImpl()
{
}

void HelloWorldClientImpl::init()
{
    auto runtime = CommonAPI::Runtime::get();
    auto proxy = runtime->buildProxy<HelloWorldProxy>("local", "demo.HelloWorld");

    std::cout << "wait proxy..." << std::endl;
    if (proxy == nullptr)
    {
        std::cout << "proxy null" << std::endl;
        return;
    }
    
    while (!proxy->isAvailable()) {
        std::this_thread::sleep_for(std::chrono::microseconds(10));
    }
    std::cout << "success connect" << std::endl;

    std::string name = "Client";
    proxy->sayHelloAsync(name, [](const CommonAPI::CallStatus& status, const std::string& message){
        if (status == CommonAPI::CallStatus::SUCCESS) {
            std::cout << "recv: " << message << std::endl;
        }  
    });

    proxy->getPowerStateAsync([](const CommonAPI::CallStatus& status, const MyTypes::PowerState& powerState){
        if (status == CommonAPI::CallStatus::SUCCESS) {
            std::cout << "PowerState: " << powerState.toString() << std::endl;
        }  
    });

    proxy->getNotifyPowerStateEvent().subscribe([](const MyTypes::PowerState& powerState){
        std::cout << "PowerState changed: " << powerState.toString() << std::endl;
    });

    while (true) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }
}