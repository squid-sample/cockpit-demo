#include "LogConfig.h"
#include <fstream>
#include <sstream>
#include <algorithm>

namespace logserver {

LogConfig::LogConfig() {
    settings_.rollPeriod = 24;
    settings_.retainDays = 7;
    settings_.maxFileSize = 1024 * 1024 * 50;
    settings_.minLogLevel = LogLevel::DEBUG;
    settings_.enabledSources = 0x0F;
    settings_.logPath = "/data/logs";
    settings_.usbMountPoint = "/mnt/usb";
    settings_.usbExportDir = "qnx_logs";
}

LogConfig::~LogConfig() {
}

LogConfig& LogConfig::getInstance() {
    static LogConfig instance;
    return instance;
}

LogSettings LogConfig::getSettings() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return settings_;
}

bool LogConfig::setSettings(const LogSettings& settings) {
    std::lock_guard<std::mutex> lock(mutex_);
    settings_ = settings;
    return saveToFile(settings_.logPath + "/logserver.conf");
}

bool LogConfig::loadFromFile(const std::string& filePath) {
    std::ifstream file(filePath);
    if (!file.is_open()) {
        return false;
    }

    std::lock_guard<std::mutex> lock(mutex_);
    LogSettings temp = settings_;
    std::string line;

    while (std::getline(file, line)) {
        size_t pos = line.find('#');
        if (pos != std::string::npos) {
            line = line.substr(0, pos);
        }
        parseConfigLine(line, temp);
    }

    settings_ = temp;
    return true;
}

bool LogConfig::saveToFile(const std::string& filePath) const {
    std::lock_guard<std::mutex> lock(mutex_);
    std::ofstream file(filePath);
    if (!file.is_open()) {
        return false;
    }

    file << "# LogServer Configuration\n";
    file << "rollPeriod=" << settings_.rollPeriod << "\n";
    file << "retainDays=" << settings_.retainDays << "\n";
    file << "maxFileSize=" << settings_.maxFileSize << "\n";
    file << "minLogLevel=" << static_cast<int>(settings_.minLogLevel) << "\n";
    file << "enabledSources=" << settings_.enabledSources << "\n";
    file << "logPath=" << settings_.logPath << "\n";
    file << "usbMountPoint=" << settings_.usbMountPoint << "\n";
    file << "usbExportDir=" << settings_.usbExportDir << "\n";

    return true;
}

bool LogConfig::parseConfigLine(const std::string& line, LogSettings& settings) {
    size_t pos = line.find('=');
    if (pos == std::string::npos) {
        return false;
    }

    std::string key = line.substr(0, pos);
    std::string value = line.substr(pos + 1);
    
    std::transform(key.begin(), key.end(), key.begin(), ::tolower);

    if (key == "rollperiod") {
        settings.rollPeriod = std::stoul(value);
    } else if (key == "retaindays") {
        settings.retainDays = std::stoul(value);
    } else if (key == "maxfilesize") {
        settings.maxFileSize = std::stoul(value);
    } else if (key == "minloglevel") {
        settings.minLogLevel = static_cast<LogLevel>(std::stoi(value));
    } else if (key == "enabledsources") {
        settings.enabledSources = std::stoul(value, nullptr, 16);
    } else if (key == "logpath") {
        settings.logPath = value;
    } else if (key == "usbmountpoint") {
        settings.usbMountPoint = value;
    } else if (key == "usbexportdir") {
        settings.usbExportDir = value;
    }

    return true;
}

}