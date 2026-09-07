#include <v1/demo/HelloWorldProxy.hpp>
#include <v1/demo/MyTypes.hpp>

using namespace v1::demo;

class HelloWorldClientImpl
{
public:
    HelloWorldClientImpl();
    ~HelloWorldClientImpl();

    void init();
};