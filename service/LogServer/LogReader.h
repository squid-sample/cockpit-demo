#ifndef LOG_READER_H
#define LOG_READER_H

#include <string>
#include <vector>
#include <cstdint>
#include "LogConfig.h"

namespace logserver {

struct LogFileInfo {
    std::string fileName;
    uint64_t fileSize;
    uint64_t createTime;
    LogSourceType sourceType;
};

class LogReader {
public:
    LogReader();
    ~LogReader();

    std::vector<LogFileInfo> getLogFiles(LogSourceType sourceType);
    std::vector<LogFileInfo> getAllLogFiles();
    std::string readLogFile(const std::string& filePath);
    bool deleteLogFile(const std::string& filePath);

private:
    std::string getSourceDirectory(LogSourceType sourceType);
};

}

#endif