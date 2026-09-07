#include "LogWriter.h"
#include "LogConfig.h"
#include <iostream>
#include <chrono>
#include <iomanip>
#include <sys/stat.h>
#include <filesystem>

namespace logserver {

LogWriter::LogWriter()
    : running_(false) {
}

LogWriter::~LogWriter() {
    stop();
}

bool LogWriter::start() {
    if (running_) {
        return true;
    }
    running_ = true;
    writerThread_ = std::thread(&LogWriter::writerThread, this);
    return true;
}

bool LogWriter::stop() {
    running_ = false;
    if (writerThread_.joinable()) {
        writerThread_.join();
    }
    for (auto& pair : fileStreams_) {
        if (pair.second.is_open()) {
            pair.second.close();
        }
    }
    return true;
}

bool LogWriter::writeLog(const LogEntry& entry) {
    std::lock_guard<std::mutex> lock(mutex_);
    logQueue_.push(entry);
    return true;
}

void LogWriter::setFileCreatedCallback(FileCreatedCallback callback) {
    fileCreatedCallback_ = callback;
}

void LogWriter::onLogFileCreated(const std::string& fileName) {
    if (fileCreatedCallback_) {
        fileCreatedCallback_(fileName);
    }
}

void LogWriter::writerThread() {
    while (running_) {
        LogEntry entry;
        bool hasEntry = false;
        {
            std::lock_guard<std::mutex> lock(mutex_);
            if (!logQueue_.empty()) {
                entry = logQueue_.front();
                logQueue_.pop();
                hasEntry = true;
            }
        }
        
        if (!hasEntry) {
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
            continue;
        }

        LogSourceType sourceType = entry.sourceType;
        auto& stream = fileStreams_[sourceType];
        auto& currentFile = currentFiles_[sourceType];
        auto& currentSize = currentFileSizes_[sourceType];

        if (!stream.is_open()) {
            if (!openNewFile(sourceType)) {
                std::cerr << "[LogWriter] Failed to open new file for source " 
                          << static_cast<int>(sourceType) << std::endl;
                continue;
            }
        }

        std::string logLine = "[" + entry.timestamp + "] "
                            + "[" + std::to_string(static_cast<int>(entry.level)) + "] "
                            + "[" + std::to_string(entry.processId) + "] "
                            + entry.message + "\n";

        stream.write(logLine.c_str(), logLine.size());
        stream.flush();
        currentSize += logLine.size();

        LogConfig& config = LogConfig::getInstance();
        LogSettings settings = config.getSettings();

        if (currentSize >= settings.maxFileSize) {
            rotateFile(sourceType);
        }
    }
}

std::string LogWriter::generateFileName(LogSourceType sourceType) {
    std::string sourcePrefix;
    switch (sourceType) {
        case LogSourceType::SYS: sourcePrefix = "sys"; break;
        case LogSourceType::APP: sourcePrefix = "app"; break;
        case LogSourceType::KERN: sourcePrefix = "kern"; break;
        case LogSourceType::MCU: sourcePrefix = "mcu"; break;
        default: sourcePrefix = "unknown";
    }

    auto now = std::chrono::system_clock::now();
    auto timeT = std::chrono::system_clock::to_time_t(now);
    std::stringstream ss;
    ss << std::put_time(std::localtime(&timeT), "%Y%m%d_%H%M%S");

    return sourcePrefix + "_" + ss.str() + ".log";
}

std::string LogWriter::getSourceDirectory(LogSourceType sourceType) {
    LogConfig& config = LogConfig::getInstance();
    LogSettings settings = config.getSettings();
    
    std::string sourceDir;
    switch (sourceType) {
        case LogSourceType::SYS: sourceDir = settings.logPath + "/sys"; break;
        case LogSourceType::APP: sourceDir = settings.logPath + "/app"; break;
        case LogSourceType::KERN: sourceDir = settings.logPath + "/kern"; break;
        case LogSourceType::MCU: sourceDir = settings.logPath + "/mcu"; break;
        default: sourceDir = settings.logPath + "/unknown";
    }

    std::filesystem::create_directories(sourceDir);
    return sourceDir;
}

bool LogWriter::openNewFile(LogSourceType sourceType) {
    std::string dir = getSourceDirectory(sourceType);
    std::string fileName = generateFileName(sourceType);
    std::string filePath = dir + "/" + fileName;

    auto& stream = fileStreams_[sourceType];
    stream.open(filePath, std::ios::out | std::ios::app);
    if (!stream.is_open()) {
        return false;
    }

    currentFiles_[sourceType] = fileName;
    currentFileSizes_[sourceType] = 0;

    onLogFileCreated(filePath);
    return true;
}

bool LogWriter::rotateFile(LogSourceType sourceType) {
    auto& stream = fileStreams_[sourceType];
    if (stream.is_open()) {
        stream.close();
    }
    return openNewFile(sourceType);
}

bool LogWriter::cleanupOldFiles() {
    LogConfig& config = LogConfig::getInstance();
    LogSettings settings = config.getSettings();

    std::vector<std::string> dirs = {
        settings.logPath + "/sys",
        settings.logPath + "/app", 
        settings.logPath + "/kern",
        settings.logPath + "/mcu"
    };

    auto now = std::chrono::system_clock::now();
    auto threshold = now - std::chrono::hours(settings.retainDays * 24);

    for (const auto& dir : dirs) {
        try {
            for (const auto& entry : std::filesystem::directory_iterator(dir)) {
                if (entry.is_regular_file()) {
                    auto ftime = std::filesystem::last_write_time(entry.path());
                    auto fileTime = std::chrono::system_clock::from_time_t(
                        std::filesystem::file_time_type::clock::to_time_t(ftime));
                    
                    if (fileTime < threshold) {
                        std::filesystem::remove(entry.path());
                    }
                }
            }
        } catch (...) {
        }
    }

    return true;
}

}