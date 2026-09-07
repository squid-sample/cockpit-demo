#include "LogManager.h"
#include <iostream>

namespace logserver {

LogManager::LogManager() {
}

LogManager::~LogManager() {
    stop();
}

bool LogManager::init() {
    logWriter_ = std::make_unique<LogWriter>();
    logReader_ = std::make_unique<LogReader>();
    logExporter_ = std::make_unique<LogExporter>();
    usbMonitor_ = std::make_unique<UsbMonitor>();

    setupLogSources();
    
    usbMonitor_->setUsbMountedCallback(
        std::bind(&LogManager::onUsbMounted, this, std::placeholders::_1));
    
    logWriter_->setFileCreatedCallback(
        std::bind(&LogManager::onLogFileCreated, this, std::placeholders::_1));

    return true;
}

bool LogManager::start() {
    LogConfig& config = LogConfig::getInstance();
    LogSettings settings = config.getSettings();

    for (auto& source : logSources_) {
        uint32_t mask = 1 << static_cast<int>(source->getSourceType());
        if (settings.enabledSources & mask) {
            source->start();
        }
    }

    logWriter_->start();
    usbMonitor_->start();

    std::cout << "[LogManager] LogServer started successfully" << std::endl;
    return true;
}

bool LogManager::stop() {
    usbMonitor_->stop();
    logWriter_->stop();

    for (auto& source : logSources_) {
        source->stop();
    }

    std::cout << "[LogManager] LogServer stopped" << std::endl;
    return true;
}

void LogManager::setupLogSources() {
    auto sysSource = std::make_unique<SysLogSource>();
    sysSource->setCallback(std::bind(&LogManager::onLogReceived, this, std::placeholders::_1));
    logSources_.push_back(std::move(sysSource));

    auto appSource = std::make_unique<AppLogSource>();
    appSource->setCallback(std::bind(&LogManager::onLogReceived, this, std::placeholders::_1));
    logSources_.push_back(std::move(appSource));

    auto kernSource = std::make_unique<KernLogSource>();
    kernSource->setCallback(std::bind(&LogManager::onLogReceived, this, std::placeholders::_1));
    logSources_.push_back(std::move(kernSource));

    auto mcuSource = std::make_unique<McuLogSource>();
    mcuSource->setCallback(std::bind(&LogManager::onLogReceived, this, std::placeholders::_1));
    logSources_.push_back(std::move(mcuSource));
}

void LogManager::onLogReceived(const LogEntry& entry) {
    LogConfig& config = LogConfig::getInstance();
    LogSettings settings = config.getSettings();

    if (entry.level >= settings.minLogLevel) {
        logWriter_->writeLog(entry);
    }
}

LogSettings LogManager::getLogSettings() {
    LogConfig& config = LogConfig::getInstance();
    return config.getSettings();
}

bool LogManager::setLogSettings(const LogSettings& settings) {
    LogConfig& config = LogConfig::getInstance();
    bool result = config.setSettings(settings);

    if (result) {
        for (auto& source : logSources_) {
            uint32_t mask = 1 << static_cast<int>(source->getSourceType());
            source->setEnabled((settings.enabledSources & mask) != 0);
        }
    }

    return result;
}

ExportResult LogManager::exportLog(LogSourceType sourceType,
                                    const std::string& startTime,
                                    const std::string& endTime,
                                    const std::string& targetPath,
                                    std::string& exportedFile) {
    return logExporter_->exportLog(sourceType, startTime, endTime, targetPath, exportedFile);
}

void LogManager::onUsbMounted(bool mounted) {
    if (mounted) {
        std::cout << "[LogManager] USB mounted, checking for export flag..." << std::endl;
        std::string exportedFile;
        ExportResult result = logExporter_->exportToUsb(exportedFile);
        
        switch (result) {
            case ExportResult::SUCCESS:
                std::cout << "[LogManager] Log export to USB successful: " << exportedFile << std::endl;
                break;
            case ExportResult::NO_FLAG:
                std::cout << "[LogManager] USB mounted but no export flag found" << std::endl;
                break;
            case ExportResult::FAILED:
                std::cout << "[LogManager] Log export to USB failed" << std::endl;
                break;
            default:
                break;
        }
    } else {
        std::cout << "[LogManager] USB unmounted" << std::endl;
    }
}

void LogManager::onLogFileCreated(const std::string& fileName) {
    if (fileCreatedCallback_) {
        fileCreatedCallback_(fileName);
    }
}

void LogManager::setFileCreatedCallback(FileCreatedCallback callback) {
    fileCreatedCallback_ = callback;
}

}