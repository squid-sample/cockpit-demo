#ifndef __LOG_SLOG2_WRITER_H__
#define __LOG_SLOG2_WRITER_H__

#include "LogWriter.h"
#include <string>

#ifdef __QNX__
#include <sys/slog2.h>
#endif

class LogSlog2Writer : public LogWriter {
public:
    LogSlog2Writer(const std::string& component = "", const std::string& buffer = "");
    ~LogSlog2Writer() override;

    bool init() override;
    void write(const LogEntry& entry) override;
    void flush() override;

    void setComponent(const std::string& component);
    void setBuffer(const std::string& buffer);

private:
#ifdef __QNX__
    slog2_buffer_t mBufferHandle;
    slog2_buffer_set_config_t mSlog2Config;
#endif
    std::string mComponent;
    std::string mBufferName;
};

#endif
