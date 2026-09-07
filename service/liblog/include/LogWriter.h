#ifndef __LOG_WRITER_H__
#define __LOG_WRITER_H__

#include "LogCommon.h"

class LogWriter {
public:
    virtual ~LogWriter() = default;
    
    virtual bool init() = 0;
    virtual void write(const LogEntry& entry) = 0;
    virtual void flush() = 0;
    
    void setLevel(LogLevel level);
    LogLevel getLevel() const;
    
    bool shouldWrite(LogLevel level) const;

protected:
    LogLevel mLevel;
};

#endif