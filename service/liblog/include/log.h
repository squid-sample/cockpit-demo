#ifndef __LOG_H__
#define __LOG_H__

#include "LogCommon.h"

#ifdef __cplusplus
extern "C" {
#endif

int log_write(LogLevel level, const char* module, const char* file, int line, const char* func, const char* format, ...);

int log_set_global_level(LogLevel level);
int log_set_module_level(const char* module, LogLevel level);

int log_init(const char* log_dir);
void log_deinit(void);

#ifdef __cplusplus
}
#endif

#ifndef LOG_TAG
#define LOG_TAG "UNKNOWN"
#endif

#define LOG_TRACE(format, ...) \
    log_write(LOG_LEVEL_TRACE, LOG_TAG, __FILE__, __LINE__, __func__, format, ##__VA_ARGS__)

#define LOG_DEBUG(format, ...) \
    log_write(LOG_LEVEL_DEBUG, LOG_TAG, __FILE__, __LINE__, __func__, format, ##__VA_ARGS__)

#define LOG_INFO(format, ...) \
    log_write(LOG_LEVEL_INFO, LOG_TAG, __FILE__, __LINE__, __func__, format, ##__VA_ARGS__)

#define LOG_WARN(format, ...) \
    log_write(LOG_LEVEL_WARN, LOG_TAG, __FILE__, __LINE__, __func__, format, ##__VA_ARGS__)

#define LOG_ERROR(format, ...) \
    log_write(LOG_LEVEL_ERROR, LOG_TAG, __FILE__, __LINE__, __func__, format, ##__VA_ARGS__)

#define LOG_FATAL(format, ...) \
    log_write(LOG_LEVEL_FATAL, LOG_TAG, __FILE__, __LINE__, __func__, format, ##__VA_ARGS__)

#endif
