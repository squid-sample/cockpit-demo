#ifndef LOG_CONFIG_H
#define LOG_CONFIG_H

#include <string>
#include <cstdint>
#include <mutex>

namespace logserver {

enum class LogLevel {
    DEBUG = 0,
    INFO = 1,
    WARN = 2,
    ERROR = 3,
    FATAL = 4
};

enum class LogSourceType {
    SYS = 0,
    APP = 1,
    KERN = 2,
    MCU = 3
};

struct LogSettings {
    uint32_t rollPeriod;
    uint32_t retainDays;
    uint32_t maxFileSize;
    LogLevel minLogLevel;
    uint32_t enabledSources;
    std::string logPath;
    std::string usbMountPoint;
    std::string usbExportDir;
};

class LogConfig {
public:
    static LogConfig& getInstance();

    LogSettings getSettings() const;
    bool setSettings(const LogSettings& settings);
    
    bool loadFromFile(const std::string& filePath);
    bool saveToFile(const std::string& filePath) const;

    LogConfig(const LogConfig&) = delete;
    LogConfig& operator=(const LogConfig&) = delete;

private:
    LogConfig();
    ~LogConfig();

    bool parseConfigLine(const std::string& line, LogSettings& settings);

    mutable std::mutex mutex_;
    LogSettings settings_;
};

}

#endif