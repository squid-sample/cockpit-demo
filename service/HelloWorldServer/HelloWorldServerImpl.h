#include <v1/demo/HelloWorldStubDefault.hpp>
#include <v1/demo/MyTypes.hpp>
#include <memory>

using namespace v1::demo;

class HelloWorldServerImpl : public HelloWorldStubDefault
{
public:
    HelloWorldServerImpl();
    ~HelloWorldServerImpl();

    void sayHello(const std::shared_ptr<CommonAPI::ClientId> _client, std::string _name, sayHelloReply_t _reply);
    void getPowerState(const std::shared_ptr<CommonAPI::ClientId> _client, getPowerStateReply_t _reply);

    void setPowerState(const MyTypes::PowerState& _status);
    const MyTypes::PowerState& getCurrentPowerState() const;

private:
    MyTypes::PowerState powerState_;
};
