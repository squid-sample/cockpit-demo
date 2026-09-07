#include "LogExporter.h"
#include "LogConfig.h"
#include "LogReader.h"
#include <iostream>
#include <filesystem>
#include <fstream>
#include <chrono>
#include <iomanip>
#include <sstream>
#include <algorithm>

#ifdef QNX
#include <sys/statfs.h>
#endif

namespace logserver {

LogExporter::LogExporter() {
}

LogExporter::~LogExporter() {
}

ExportResult LogExporter::exportLog(LogSourceType sourceType,
                                     const std::string& startTime,
                                     const std::string& endTime,
                                     const std::string& targetPath,
                                     std::string& exportedFile) {
    std::vector<std::string> files = getFilesToExport(sourceType, startTime, endTime);
    if (files.empty()) {
        return ExportResult::FAILED;
    }

    std::filesystem::create_directories(targetPath);
    
    auto now = std::chrono::system_clock::now();
    auto timeT = std::chrono::system_clock::to_time_t(now);
    std::stringstream ss;
    ss << std::put_time(std::localtime(&timeT), "%Y%m%d_%H%M%S");
    
    exportedFile = targetPath + "/log_export_" + ss.str() + ".zip";
    
    if (!createZip(files, exportedFile)) {
        return ExportResult::FAILED;
    }

    return ExportResult::SUCCESS;
}

ExportResult LogExporter::exportAllLogs(const std::string& targetPath,
                                         std::string& exportedFile) {
    LogReader reader;
    auto files = reader.getAllLogFiles();
    
    std::vector<std::string> filePaths;
    LogConfig& config = LogConfig::getInstance();
    LogSettings settings = config.getSettings();
    
    for (const auto& file : files) {
        std::string dir = settings.logPath;
        switch (file.sourceType) {
            case LogSourceType::SYS: dir += "/sys"; break;
            case LogSourceType::APP: dir += "/app"; break;
            case LogSourceType::KERN: dir += "/kern"; break;
            case LogSourceType::MCU: dir += "/mcu"; break;
            default: dir += "/unknown";
        }
        filePaths.push_back(dir + "/" + file.fileName);
    }

    if (filePaths.empty()) {
        return ExportResult::FAILED;
    }

    std::filesystem::create_directories(targetPath);
    
    auto now = std::chrono::system_clock::now();
    auto timeT = std::chrono::system_clock::to_time_t(now);
    std::stringstream ss;
    ss << std::put_time(std::localtime(&timeT), "%Y%m%d_%H%M%S");
    
    exportedFile = targetPath + "/log_export_all_" + ss.str() + ".zip";
    
    if (!createZip(filePaths, exportedFile)) {
        return ExportResult::FAILED;
    }

    return ExportResult::SUCCESS;
}

ExportResult LogExporter::exportToUsb(std::string& exportedFile) {
    if (!checkUsbMounted()) {
        return ExportResult::NO_USB;
    }

    if (!checkExportFlag()) {
        return ExportResult::NO_FLAG;
    }

    LogConfig& config = LogConfig::getInstance();
    LogSettings settings = config.getSettings();
    
    std::string targetPath = settings.usbMountPoint + "/" + settings.usbExportDir;
    
    ExportResult result = exportAllLogs(targetPath, exportedFile);
    
    if (result == ExportResult::SUCCESS) {
        removeExportFlag();
        createExportDoneFlag();
    }

    return result;
}

std::vector<std::string> LogExporter::getFilesToExport(LogSourceType sourceType,
                                                        const std::string& startTime,
                                                        const std::string& endTime) {
    LogReader reader;
    auto files = reader.getLogFiles(sourceType);
    
    std::vector<std::string> filePaths;
    LogConfig& config = LogConfig::getInstance();
    LogSettings settings = config.getSettings();
    
    std::string dir = settings.logPath;
    switch (sourceType) {
        case LogSourceType::SYS: dir += "/sys"; break;
        case LogSourceType::APP: dir += "/app"; break;
        case LogSourceType::KERN: dir += "/kern"; break;
        case LogSourceType::MCU: dir += "/mcu"; break;
        default: dir += "/unknown";
    }
    
    for (const auto& file : files) {
        filePaths.push_back(dir + "/" + file.fileName);
    }

    return filePaths;
}

bool LogExporter::checkUsbMounted() {
    LogConfig& config = LogConfig::getInstance();
    LogSettings settings = config.getSettings();
    
    std::filesystem::path mountPath(settings.usbMountPoint);
    return std::filesystem::exists(mountPath) && std::filesystem::is_directory(mountPath);
}

bool LogExporter::checkExportFlag() {
    LogConfig& config = LogConfig::getInstance();
    LogSettings settings = config.getSettings();
    
    std::string flagPath = settings.logPath + "/export.flag";
    return std::filesystem::exists(flagPath);
}

void LogExporter::removeExportFlag() {
    LogConfig& config = LogConfig::getInstance();
    LogSettings settings = config.getSettings();
    
    std::string flagPath = settings.logPath + "/export.flag";
    std::filesystem::remove(flagPath);
}

void LogExporter::createExportDoneFlag() {
    LogConfig& config = LogConfig::getInstance();
    LogSettings settings = config.getSettings();
    
    std::string donePath = settings.usbMountPoint + "/" + settings.usbExportDir + "/export_done.flag";
    std::ofstream file(donePath);
    if (file.is_open()) {
        file.close();
    }
}

bool LogExporter::createZip(const std::vector<std::string>& files,
                             const std::string& outputPath) {
    for (const auto& file : files) {
        std::string destFile = outputPath + ".tmp/" + std::filesystem::path(file).filename().string();
        std::filesystem::create_directories(std::filesystem::path(destFile).parent_path());
        try {
            std::filesystem::copy_file(file, destFile, std::filesystem::copy_options::overwrite_existing);
        } catch (...) {
        }
    }
    
    return true;
}

bool LogExporter::copyFiles(const std::vector<std::string>& files,
                             const std::string& targetDir) {
    std::filesystem::create_directories(targetDir);
    
    for (const auto& file : files) {
        std::string destFile = targetDir + "/" + std::filesystem::path(file).filename().string();
        try {
            std::filesystem::copy_file(file, destFile, std::filesystem::copy_options::overwrite_existing);
        } catch (...) {
            return false;
        }
    }
    
    return true;
}

}