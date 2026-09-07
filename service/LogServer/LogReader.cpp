#include "LogReader.h"
#include "LogConfig.h"
#include <fstream>
#include <filesystem>
#include <sstream>

namespace logserver {

LogReader::LogReader() {
}

LogReader::~LogReader() {
}

std::string LogReader::getSourceDirectory(LogSourceType sourceType) {
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

    return sourceDir;
}

std::vector<LogFileInfo> LogReader::getLogFiles(LogSourceType sourceType) {
    std::vector<LogFileInfo> files;
    std::string dir = getSourceDirectory(sourceType);

    try {
        for (const auto& entry : std::filesystem::directory_iterator(dir)) {
            if (entry.is_regular_file() && entry.path().extension() == ".log") {
                LogFileInfo info;
                info.fileName = entry.path().filename().string();
                info.fileSize = std::filesystem::file_size(entry.path());
                info.createTime = std::filesystem::last_write_time(entry.path())
                    .time_since_epoch().count();
                info.sourceType = sourceType;
                files.push_back(info);
            }
        }
    } catch (...) {
    }

    return files;
}

std::vector<LogFileInfo> LogReader::getAllLogFiles() {
    std::vector<LogFileInfo> allFiles;
    
    for (int i = 0; i < 4; ++i) {
        auto files = getLogFiles(static_cast<LogSourceType>(i));
        allFiles.insert(allFiles.end(), files.begin(), files.end());
    }

    return allFiles;
}

std::string LogReader::readLogFile(const std::string& filePath) {
    std::ifstream file(filePath);
    if (!file.is_open()) {
        return "";
    }

    std::stringstream buffer;
    buffer << file.rdbuf();
    return buffer.str();
}

bool LogReader::deleteLogFile(const std::string& filePath) {
    try {
        return std::filesystem::remove(filePath);
    } catch (...) {
        return false;
    }
}

}