#ifndef __LOG_MANAGER_H__
#define __LOG_MANAGER_H__

#include "LogCommon.h"
#include "Singleton.h"
#include <string>
#include <map>
#include <vector>

class LogWriter;

class LogManager {
DECLARE_SINGLETON_FRIEND(LogManager)

public:
    bool init();
    void destroy();

    void setGlobalLevel(LogLevel level);
    LogLevel getGlobalLevel() const;

    void setModuleLevel(const std::string& module, LogLevel level);
    LogLevel getModuleLevel(const std::string& module) const;

    void addWriter(LogWriter* writer);
    void removeWriter(LogWriter* writer);

    void writeLog(const LogEntry& entry);

    void setLogDir(const std::string& dir);
    std::string getLogDir() const;

    void setConsoleEnabled(bool enabled);
    bool getConsoleEnabled() const;

    void setFileEnabled(bool enabled);
    bool getFileEnabled() const;

    void setMaxFileSize(size_t size);
    size_t getMaxFileSize() const;

    void setMaxFiles(int count);
    int getMaxFiles() const;

private:
    LogManager();
    ~LogManager();

    LogLevel mGlobalLevel;
    std::string mLogDir;
    std::map<std::string, LogLevel> mModuleLevels;
    std::vector<LogWriter*> mWriters;
    bool mInitialized;
    bool mConsoleEnabled;
    bool mFileEnabled;
    size_t mMaxFileSize;
    int mMaxFiles;
};

#endif