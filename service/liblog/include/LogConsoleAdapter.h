#ifndef __LOG_CONSOLE_ADAPTER_H__
#define __LOG_CONSOLE_ADAPTER_H__

#include "LogWriter.h"

class LogConsoleAdapter : public LogWriter {
public:
    LogConsoleAdapter();
    ~LogConsoleAdapter() override;

    bool init() override;
    void write(const LogEntry& entry) override;
    void flush() override;
};

#endif