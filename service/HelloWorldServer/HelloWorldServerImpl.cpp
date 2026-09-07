#include "HelloWorldServerImpl.h"

#include <string>
#include <iostream>

HelloWorldServerImpl::HelloWorldServerImpl()
    : powerState_(MyTypes::PowerState::OFF)
{

}

HelloWorldServerImpl::~HelloWorldServerImpl()
{

}

void HelloWorldServerImpl::sayHello(const std::shared_ptr<CommonAPI::ClientId> _client, std::string _name, sayHelloReply_t _reply)
{
    std::string response = "Hello, " + _name;
    std::cout << "[Server] sayHello called with name: " << _name << std::endl;
    _reply(response);
}

void HelloWorldServerImpl::getPowerState(const std::shared_ptr<CommonAPI::ClientId> _client, getPowerStateReply_t _reply)
{
    std::cout << "[Server] getPowerState called, current state: " << powerState_.toString() << std::endl;
    _reply(powerState_);
}

void HelloWorldServerImpl::setPowerState(const MyTypes::PowerState& _status)
{
    if (powerState_ != _status) {
        powerState_ = _status;
        std::cout << "[Server] PowerState changed to: " << powerState_.toString() << std::endl;
        fireNotifyPowerStateEvent(powerState_);
    }
}

const MyTypes::PowerState& HelloWorldServerImpl::getCurrentPowerState() const
{
    return powerState_;
}