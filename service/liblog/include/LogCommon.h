#ifndef __LOG_COMMON_H__
#define __LOG_COMMON_H__

#include <stdint.h>
#include <time.h>
#include <string.h>

#ifdef _WIN32
#include <windows.h>
#include <process.h>
#define getpid() _getpid()
#define gettid() GetCurrentThreadId()
#elif defined(__QNX__)
#include <sys/types.h>
#include <sys/neutrino.h>
#include <unistd.h>
#include <pthread.h>
#ifdef __cplusplus
extern "C" {
#endif
extern pid_t getpid(void);
#ifdef __cplusplus
}
#endif
#define gettid()  ((uint32_t)(uintptr_t)pthread_self())
#else
#include <sys/types.h>
#include <unistd.h>
#include <pthread.h>
#define gettid() pthread_self()
#endif

const char* get_basename(const char* path);

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    LOG_LEVEL_TRACE = 0,
    LOG_LEVEL_DEBUG = 1,
    LOG_LEVEL_INFO  = 2,
    LOG_LEVEL_WARN  = 3,
    LOG_LEVEL_ERROR = 4,
    LOG_LEVEL_FATAL = 5,
    LOG_LEVEL_MAX
} LogLevel;

typedef struct {
    LogLevel level;
    uint64_t timestamp;
    const char* module;
    uint32_t pid;
    uint32_t tid;
    const char* file;
    int line;
    const char* func;
    const char* message;
} LogEntry;

const char* log_level_to_string(LogLevel level);

#define LOG_MODULE_MAX_NAME 32
#define LOG_MESSAGE_MAX_LEN 4096

#ifdef __cplusplus
}
#endif

#endif