#include "LogSlog2Writer.h"
#include "LogCommon.h"
#include <cstdio>
#include <cstring>
#include <stdarg.h>

LogSlog2Writer::LogSlog2Writer(const std::string& component, const std::string& buffer)
    : mComponent(component), mBufferName(buffer) {
    mLevel = LOG_LEVEL_INFO;
#ifdef __QNX__
    mBufferHandle = NULL;
#endif
}

LogSlog2Writer::~LogSlog2Writer() {
#ifdef __QNX__
    if (mBufferHandle) {
        slog2_reset();
        mBufferHandle = NULL;
    }
#endif
}

bool LogSlog2Writer::init() {
#ifdef __QNX__
    if (mComponent.empty()) {
        mComponent = "LogService";
    }
    if (mBufferName.empty()) {
        mBufferName = "main";
    }

    memset(&mSlog2Config, 0, sizeof(mSlog2Config));
    mSlog2Config.num_buffers = 1;
    mSlog2Config.buffer_set_name = mComponent.c_str();
    mSlog2Config.verbosity_level = SLOG2_INFO;
    mSlog2Config.buffer_config[0].buffer_name = mBufferName.c_str();
    mSlog2Config.buffer_config[0].num_pages = 4;

    slog2_buffer_t handles[SLOG2_MAX_BUFFERS];
    if (slog2_register(&mSlog2Config, handles, 0) != 0) {
        return false;
    }
    mBufferHandle = handles[0];
#endif
    return true;
}

void LogSlog2Writer::write(const LogEntry& entry) {
#ifdef __QNX__
    if (!mBufferHandle) {
        return;
    }

    _Uint8t slog_severity;
    switch (entry.level) {
        case LOG_LEVEL_TRACE:
        case LOG_LEVEL_DEBUG:
            slog_severity = SLOG2_DEBUG1;
            break;
        case LOG_LEVEL_INFO:
            slog_severity = SLOG2_INFO;
            break;
        case LOG_LEVEL_WARN:
            slog_severity = SLOG2_WARNING;
            break;
        case LOG_LEVEL_ERROR:
            slog_severity = SLOG2_ERROR;
            break;
        case LOG_LEVEL_FATAL:
            slog_severity = SLOG2_CRITICAL;
            break;
        default:
            slog_severity = SLOG2_INFO;
            break;
    }

    slog2f(mBufferHandle, 0, slog_severity,
           "[%s] [%s:%d] %s",
           entry.module, entry.file, entry.line, entry.message);
#else
    (void)entry;
#endif
}

void LogSlog2Writer::flush() {
#ifdef __QNX__
    // slog2 uses shared memory buffers, no explicit flush needed in SDP 8.0
    if (mBufferHandle) {
        (void)mBufferHandle;
    }
#endif
}

void LogSlog2Writer::setComponent(const std::string& component) {
    mComponent = component;
}

void LogSlog2Writer::setBuffer(const std::string& buffer) {
    mBufferName = buffer;
}
