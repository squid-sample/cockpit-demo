#ifndef LOG_EXPORTER_H
#define LOG_EXPORTER_H

#include <string>
#include <vector>
#include <cstdint>
#include "LogConfig.h"
#include "LogReader.h"

namespace logserver {

enum class ExportResult {
    SUCCESS = 0,
    FAILED = 1,
    NO_USB = 2,
    NO_FLAG = 3
};

class LogExporter {
public:
    LogExporter();
    ~LogExporter();

    ExportResult exportLog(LogSourceType sourceType, 
                           const std::string& startTime,
                           const std::string& endTime,
                           const std::string& targetPath,
                           std::string& exportedFile);

    ExportResult exportAllLogs(const std::string& targetPath,
                               std::string& exportedFile);

    ExportResult exportToUsb(std::string& exportedFile);

private:
    bool createZip(const std::vector<std::string>& files, 
                   const std::string& outputPath);
    bool copyFiles(const std::vector<std::string>& files, 
                   const std::string& targetDir);
    std::vector<std::string> getFilesToExport(LogSourceType sourceType,
                                               const std::string& startTime,
                                               const std::string& endTime);
    bool checkUsbMounted();
    bool checkExportFlag();
    void removeExportFlag();
    void createExportDoneFlag();
};

}

#endif