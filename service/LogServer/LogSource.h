#ifndef LOG_SOURCE_H
#define LOG_SOURCE_H

#include <string>
#include <cstdint>
#include <memory>
#include <functional>
#include <thread>
#include "LogConfig.h"

namespace logserver {

struct LogEntry {
    std::string timestamp;
    LogLevel level;
    LogSourceType sourceType;
    uint32_t processId;
    std::string processName;
    std::string functionName;
    std::string message;
};

using LogCallback = std::function<void(const LogEntry&)>;

class LogSource {
public:
    LogSource(LogSourceType type);
    virtual ~LogSource();

    virtual bool start() = 0;
    virtual bool stop() = 0;
    virtual LogSourceType getSourceType() const;

    void setCallback(LogCallback callback);
    void setEnabled(bool enabled);
    bool isEnabled() const;

protected:
    void notify(const LogEntry& entry);

private:
    LogSourceType sourceType_;
    LogCallback callback_;
    bool enabled_;
};

class SysLogSource : public LogSource {
public:
    SysLogSource();
    ~SysLogSource();

    bool start() override;
    bool stop() override;

private:
#ifdef QNX
    void slog2ReaderThread();
    int slog2Handle_;
#endif
    bool running_;
    std::thread readerThread_;
};

class AppLogSource : public LogSource {
public:
    AppLogSource();
    ~AppLogSource();

    bool start() override;
    bool stop() override;

private:
    void fileMonitorThread();
    bool running_;
    std::thread monitorThread_;
};

class KernLogSource : public LogSource {
public:
    KernLogSource();
    ~KernLogSource();

    bool start() override;
    bool stop() override;

private:
    void kernLogReaderThread();
    bool running_;
    std::thread readerThread_;
};

class McuLogSource : public LogSource {
public:
    McuLogSource();
    ~McuLogSource();

    bool start() override;
    bool stop() override;

private:
    void mcuLogReaderThread();
    bool running_;
    std::thread readerThread_;
};

}

#endif