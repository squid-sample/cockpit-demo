#ifndef USB_MONITOR_H
#define USB_MONITOR_H

#include <string>
#include <thread>
#include <atomic>
#include <functional>
#include "LogConfig.h"

namespace logserver {

class UsbMonitor {
public:
    UsbMonitor();
    ~UsbMonitor();

    bool start();
    bool stop();

    using UsbMountedCallback = std::function<void(bool)>;
    void setUsbMountedCallback(UsbMountedCallback callback);

private:
    void monitorThread();
    bool checkUsbMounted();

    std::atomic<bool> running_;
    std::thread monitorThread_;
    UsbMountedCallback callback_;
    bool lastMountedState_;
};

}

#endif