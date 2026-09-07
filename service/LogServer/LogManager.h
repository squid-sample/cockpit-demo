#ifndef LOG_MANAGER_H
#define LOG_MANAGER_H

#include <memory>
#include <vector>
#include <string>
#include "LogConfig.h"
#include "LogSource.h"
#include "LogWriter.h"
#include "LogReader.h"
#include "LogExporter.h"
#include "UsbMonitor.h"

namespace logserver {

class LogManager {
public:
    LogManager();
    ~LogManager();

    bool init();
    bool start();
    bool stop();

    LogSettings getLogSettings();
    bool setLogSettings(const LogSettings& settings);

    ExportResult exportLog(LogSourceType sourceType,
                           const std::string& startTime,
                           const std::string& endTime,
                           const std::string& targetPath,
                           std::string& exportedFile);

    void onUsbMounted(bool mounted);
    void onLogFileCreated(const std::string& fileName);

    using FileCreatedCallback = std::function<void(const std::string&)>;
    void setFileCreatedCallback(FileCreatedCallback callback);

private:
    void setupLogSources();
    void onLogReceived(const LogEntry& entry);

    std::unique_ptr<LogConfig> config_;
    std::vector<std::unique_ptr<LogSource>> logSources_;
    std::unique_ptr<LogWriter> logWriter_;
    std::unique_ptr<LogReader> logReader_;
    std::unique_ptr<LogExporter> logExporter_;
    std::unique_ptr<UsbMonitor> usbMonitor_;

    FileCreatedCallback fileCreatedCallback_;
};

}

#endif