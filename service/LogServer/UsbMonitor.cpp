#include "UsbMonitor.h"
#include "LogConfig.h"
#include <filesystem>
#include <iostream>

namespace logserver {

UsbMonitor::UsbMonitor()
    : running_(false), lastMountedState_(false) {
}

UsbMonitor::~UsbMonitor() {
    stop();
}

bool UsbMonitor::start() {
    if (running_) {
        return true;
    }
    running_ = true;
    monitorThread_ = std::thread(&UsbMonitor::monitorThread, this);
    return true;
}

bool UsbMonitor::stop() {
    running_ = false;
    if (monitorThread_.joinable()) {
        monitorThread_.join();
    }
    return true;
}

void UsbMonitor::setUsbMountedCallback(UsbMountedCallback callback) {
    callback_ = callback;
}

void UsbMonitor::monitorThread() {
    while (running_) {
        bool mounted = checkUsbMounted();
        
        if (mounted != lastMountedState_) {
            lastMountedState_ = mounted;
            if (callback_) {
                callback_(mounted);
            }
        }
        
        std::this_thread::sleep_for(std::chrono::seconds(2));
    }
}

bool UsbMonitor::checkUsbMounted() {
    LogConfig& config = LogConfig::getInstance();
    LogSettings settings = config.getSettings();
    
    std::filesystem::path mountPath(settings.usbMountPoint);
    return std::filesystem::exists(mountPath) && std::filesystem::is_directory(mountPath);
}

}