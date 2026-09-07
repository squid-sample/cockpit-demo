#ifndef LOG_WRITER_H
#define LOG_WRITER_H

#include <string>
#include <cstdint>
#include <fstream>
#include <mutex>
#include <queue>
#include <thread>
#include <atomic>
#include <map>
#include "LogSource.h"

namespace logserver {

class LogWriter {
public:
    LogWriter();
    ~LogWriter();

    bool start();
    bool stop();
    bool writeLog(const LogEntry& entry);
    
    void onLogFileCreated(const std::string& fileName);
    using FileCreatedCallback = std::function<void(const std::string&)>;
    void setFileCreatedCallback(FileCreatedCallback callback);

private:
    void writerThread();
    std::string generateFileName(LogSourceType sourceType);
    std::string getSourceDirectory(LogSourceType sourceType);
    bool openNewFile(LogSourceType sourceType);
    bool rotateFile(LogSourceType sourceType);
    bool cleanupOldFiles();

    std::mutex mutex_;
    std::queue<LogEntry> logQueue_;
    std::atomic<bool> running_;
    std::thread writerThread_;

    std::map<LogSourceType, std::ofstream> fileStreams_;
    std::map<LogSourceType, std::string> currentFiles_;
    std::map<LogSourceType, uint64_t> currentFileSizes_;

    FileCreatedCallback fileCreatedCallback_;
};

}

#endif