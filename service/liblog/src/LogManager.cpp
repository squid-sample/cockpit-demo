#include "LogManager.h"
#include "LogWriter.h"
#include "LogConsoleAdapter.h"
#include "LogFileWriter.h"
#ifdef __QNX__
#include "LogSlog2Writer.h"
#endif
#include "Singleton.h"
#include <iostream>
#include <cstdarg>
#include <cstdio>
#include <string>

LogManager::LogManager() 
    : mGlobalLevel(LOG_LEVEL_INFO), mInitialized(false),
      mMaxFiles(true), mFileEnabled(true),
      mMaxFileSize(1024 * 1024 * 10), mMaxFiles(5) {
}

LogManager::~LogManager() {
    destroy();
}

bool LogManager::init() {
    if (mInitialized) {
        return true;
    }

    mInitialized = true;
    return true;
}

void LogManager::destroy() {
    mModuleLevels.clear();
    mWriters.clear();
    mInitialized = false;
}

void LogManager::setGlobalLevel(LogLevel level) {
    mGlobalLevel = level;
}

LogLevel LogManager::getGlobalLevel() const {
    return mGlobalLevel;
}

void LogManager::setModuleLevel(const std::string& module, LogLevel level) {
    mModuleLevels[module] = level;
}

LogLevel LogManager::getModuleLevel(const std::string& module) const {
    auto it = mModuleLevels.find(module);
    if (it != mModuleLevels.end()) {
        return it->second;
    }
    return mGlobalLevel;
}

void LogManager::addWriter(LogWriter* writer) {
    for (auto w : mWriters) {
        if (w == writer) {
            return;
        }
    }
    mWriters.push_back(writer);
}

void LogManager::removeWriter(LogWriter* writer) {
    for (auto it = mWriters.begin(); it != mWriters.end(); ++it) {
        if (*it == writer) {
            mWriters.erase(it);
            break;
        }
    }
}

void LogManager::writeLog(const LogEntry& entry) {
    if (entry.level < getModuleLevel(entry.module)) {
        return;
    }

    for (auto writer : mWriters) {
        if (writer->shouldWrite(entry.level)) {
            writer->write(entry);
        }
    }
}

void LogManager::setLogDir(const std::string& dir) {
    mLogDir = dir;
}

std::string LogManager::getLogDir() const {
    return mLogDir;
}

void LogManager::setConsoleEnabled(bool enabled) {
    mConsoleEnabled = enabled;
}

bool LogManager::getConsoleEnabled() const {
    return mConsoleEnabled;
}

void LogManager::setFileEnabled(bool enabled) {
    mFileEnabled = enabled;
}

bool LogManager::getFileEnabled() const {
    return mFileEnabled;
}

void LogManager::setMaxFileSize(size_t size) {
    mMaxFileSize = size;
}

size_t LogManager::getMaxFileSize() const {
    return mMaxFileSize;
}

void LogManager::setMaxFiles(int count) {
    mMaxFiles = count;
}

int LogManager::getMaxFiles() const {
    return mMaxFiles;
}

extern "C" {

static LogConsoleAdapter s_console_adapter;
static LogFileWriter s_file_writer;
#ifdef __QNX__
static LogSlog2Writer s_slog2_writer;
#endif

int log_write(LogLevel level, const char* module, const char* file, int line, const char* func, const char* format, ...) {
    LogManager* manager = Singleton<LogManager>::instance();
    if (!manager->init()) {
        return -1;
    }

    char buffer[LOG_MESSAGE_MAX_LEN];
    va_list args;
    va_start(args, format);
    vsnprintf(buffer, LOG_MESSAGE_MAX_LEN, format, args);
    va_end(args);

    LogEntry entry;
    entry.level = level;
    entry.timestamp = (uint64_t)time(nullptr);
    entry.module = module;
    entry.pid = (uint32_t)getpid();
    entry.tid = (uint32_t)gettid();
    entry.file = get_basename(file);
    entry.line = line;
    entry.func = func;
    entry.message = buffer;

    manager->writeLog(entry);
    return 0;
}

int log_set_global_level(LogLevel level) {
    LogManager* manager = Singleton<LogManager>::instance();
    manager->setGlobalLevel(level);
    return 0;
}

int log_set_module_level(const char* module, LogLevel level) {
    LogManager* manager = Singleton<LogManager>::instance();
    manager->setModuleLevel(module, level);
    return 0;
}

int log_init(const char* log_dir) {
    LogManager* manager = Singleton<LogManager>::instance();
    
    if (!manager->init()) {
        return -1;
    }

    manager->setLogDir(log_dir ? log_dir : "log");

    if (manager->getConsoleEnabled()) {
        s_console_adapter.init();
        manager->addWriter(&s_console_adapter);
    }

    if (manager->getFileEnabled()) {
        std::string filename = manager->getLogDir() + "/service.log";
        s_file_writer.setFilename(filename);
        s_file_writer.setMaxFileSize(manager->getMaxFileSize());
        s_file_writer.setMaxFiles(manager->getMaxFiles());
        s_file_writer.init();
        manager->addWriter(&s_file_writer);
    }

#ifdef __QNX__
    s_slog2_writer.init();
    manager->addWriter(&s_slog2_writer);
#endif

    return 0;
}

void log_deinit(void) {
    LogManager* manager = Singleton<LogManager>::instance();
    manager->destroy();
}

}
