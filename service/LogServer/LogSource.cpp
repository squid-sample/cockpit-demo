#include "LogSource.h"
#include <iostream>
#include <fstream>
#include <chrono>
#include <iomanip>

#ifdef QNX
#include <sys/slog2.h>
#include <sys/neutrino.h>
#endif

namespace logserver {

LogSource::LogSource(LogSourceType type)
    : sourceType_(type), enabled_(true) {
}

LogSource::~LogSource() {
}

LogSourceType LogSource::getSourceType() const {
    return sourceType_;
}

void LogSource::setCallback(LogCallback callback) {
    callback_ = callback;
}

void LogSource::setEnabled(bool enabled) {
    enabled_ = enabled;
}

bool LogSource::isEnabled() const {
    return enabled_;
}

void LogSource::notify(const LogEntry& entry) {
    if (enabled_ && callback_) {
        callback_(entry);
    }
}

SysLogSource::SysLogSource()
    : LogSource(LogSourceType::SYS), running_(false) {
#ifdef QNX
    slog2Handle_ = -1;
#endif
}

SysLogSource::~SysLogSource() {
    stop();
}

bool SysLogSource::start() {
    if (running_) {
        return true;
    }

#ifdef QNX
    slog2_handle_t handle = slog2_open("logserver", 0, SLOG2_MODE_RDWR, 0);
    if (handle == SLOG2_HANDLE_INVALID) {
        std::cerr << "[LogSource] Failed to open slog2" << std::endl;
        return false;
    }
    slog2Handle_ = handle;
#endif

    running_ = true;
    readerThread_ = std::thread(&SysLogSource::slog2ReaderThread, this);
    return true;
}

bool SysLogSource::stop() {
    running_ = false;
    if (readerThread_.joinable()) {
        readerThread_.join();
    }
#ifdef QNX
    if (slog2Handle_ >= 0) {
        slog2_close(slog2Handle_);
        slog2Handle_ = -1;
    }
#endif
    return true;
}

#ifdef QNX
void SysLogSource::slog2ReaderThread() {
    while (running_) {
        slog2_buffer_set_t bufferSet;
        slog2_buffer_t buffer;
        slog2_entry_t entry;
        
        if (slog2_get_next_buffer_set(slog2Handle_, &bufferSet, -1) != SLOG2_OK) {
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
            continue;
        }

        while (slog2_get_next_buffer(bufferSet, &buffer) == SLOG2_OK) {
            while (slog2_get_next_entry(buffer, &entry) == SLOG2_OK) {
                LogEntry logEntry;
                logEntry.sourceType = LogSourceType::SYS;
                logEntry.processId = entry.pid;
                logEntry.message = entry.data;
                
                auto now = std::chrono::system_clock::now();
                auto timeT = std::chrono::system_clock::to_time_t(now);
                std::stringstream ss;
                ss << std::put_time(std::localtime(&timeT), "%Y-%m-%d %H:%M:%S");
                logEntry.timestamp = ss.str();

                notify(logEntry);
            }
        }

        slog2_release_buffer_set(bufferSet);
    }
}
#else
void SysLogSource::slog2ReaderThread() {
    while (running_) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }
}
#endif

AppLogSource::AppLogSource()
    : LogSource(LogSourceType::APP), running_(false) {
}

AppLogSource::~AppLogSource() {
    stop();
}

bool AppLogSource::start() {
    if (running_) {
        return true;
    }
    running_ = true;
    monitorThread_ = std::thread(&AppLogSource::fileMonitorThread, this);
    return true;
}

bool AppLogSource::stop() {
    running_ = false;
    if (monitorThread_.joinable()) {
        monitorThread_.join();
    }
    return true;
}

void AppLogSource::fileMonitorThread() {
    while (running_) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }
}

KernLogSource::KernLogSource()
    : LogSource(LogSourceType::KERN), running_(false) {
}

KernLogSource::~KernLogSource() {
    stop();
}

bool KernLogSource::start() {
    if (running_) {
        return true;
    }
    running_ = true;
    readerThread_ = std::thread(&KernLogSource::kernLogReaderThread, this);
    return true;
}

bool KernLogSource::stop() {
    running_ = false;
    if (readerThread_.joinable()) {
        readerThread_.join();
    }
    return true;
}

void KernLogSource::kernLogReaderThread() {
    while (running_) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }
}

McuLogSource::McuLogSource()
    : LogSource(LogSourceType::MCU), running_(false) {
}

McuLogSource::~McuLogSource() {
    stop();
}

bool McuLogSource::start() {
    if (running_) {
        return true;
    }
    running_ = true;
    readerThread_ = std::thread(&McuLogSource::mcuLogReaderThread, this);
    return true;
}

bool McuLogSource::stop() {
    running_ = false;
    if (readerThread_.joinable()) {
        readerThread_.join();
    }
    return true;
}

void McuLogSource::mcuLogReaderThread() {
    while (running_) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }
}

}