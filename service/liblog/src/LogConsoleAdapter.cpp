#include "LogConsoleAdapter.h"
#include "LogCommon.h"
#include <cstdio>
#include <time.h>

LogConsoleAdapter::LogConsoleAdapter() {
    mLevel = LOG_LEVEL_INFO;
} 

LogConsoleAdapter::~LogConsoleAdapter() {
}

bool LogConsoleAdapter::init() {
    return true;
}

void LogConsoleAdapter::write(const LogEntry& entry) {
    time_t t = (time_t)entry.timestamp;
    struct tm* tm_info = localtime(&t);
    char time_str[32];
    strftime(time_str, sizeof(time_str), "%Y-%m-%d %H:%M:%S", tm_info);

    printf("[%s] [%s] [%s] [P:%u T:%u] [%s:%d:%s] %s\n", 
           time_str, 
           log_level_to_string(entry.level),
           entry.module,
           entry.pid,
           entry.tid,
           entry.file,
           entry.line,
           entry.func,
           entry.message);
}

void LogConsoleAdapter::flush() {
    fflush(stdout);
}
