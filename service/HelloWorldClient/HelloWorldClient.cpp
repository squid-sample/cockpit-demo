#include <iostream>
#include "HelloWorldClientImpl.h"

int main()
{
    auto service = std::make_shared<HelloWorldClientImpl>();
    std::cout << "Client------>" << std::endl;
    service->init();
    return 0;
}