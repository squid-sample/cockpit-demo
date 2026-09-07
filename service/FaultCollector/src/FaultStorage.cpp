#define LOG_TAG "FaultCollector"
#include "log.h"

#include "FaultStorage.h"
#include <fstream>
#include <sys/stat.h>
#include <dirent.h>
#include <algorithm>
#include <mutex>
#include <thread>
#include <atomic>
#include <condition_variable>
#include <queue>

FaultStorage::FaultStorage() : mInitialized(false), mFlushThreadRunning(false) {
}

FaultStorage::~FaultStorage() {
    destroy();
}

bool FaultStorage::init(const std::string& path) {
    mStoragePath = path;
    
    if (!ensureDirectory()) {
        LOG_ERROR("failed to create storage directory: %s", mStoragePath.c_str());
        return false;
    }

    mFlushThreadRunning = true;
    mFlushThread = std::thread(&FaultStorage::flushLoop, this);

    mInitialized = true;
    return true;
}

void FaultStorage::destroy() {
    if (mFlushThreadRunning) {
        mFlushThreadRunning = false;
        mFlushCondition.notify_one();
        if (mFlushThread.joinable()) {
            mFlushThread.join();
        }
    }
    mInitialized = false;
}

bool FaultStorage::ensureDirectory() {
    struct stat st;
    if (stat(mStoragePath.c_str(), &st) != 0) {
        if (mkdir(mStoragePath.c_str(), 0755) != 0) {
            return false;
        }
    }
    return true;
}

std::string FaultStorage::getFaultFilePath() {
    return mStoragePath + "/faults.dat";
}

bool FaultStorage::saveFault(const FaultInfo& fault_info) {
    if (!mInitialized) {
        return false;
    }

    std::lock_guard<std::mutex> lock(mCacheMutex);
    mPendingFaults.push(fault_info);
    mFlushCondition.notify_one();

    return true;
}

bool FaultStorage::saveFaultSync(const FaultInfo& fault_info) {
    if (!mInitialized) {
        return false;
    }

    std::string filepath = getFaultFilePath();
    std::fstream file(filepath, std::ios::binary | std::ios::in | std::ios::out | std::ios::ate);
    
    if (!file) {
        file.open(filepath, std::ios::binary | std::ios::out);
        if (!file) {
            LOG_ERROR("failed to open fault file: %s", filepath.c_str());
            return false;
        }
    }

    file.write((const char*)&fault_info, sizeof(fault_info));
    file.close();

    return true;
}

void FaultStorage::flushLoop() {
    while (mFlushThreadRunning) {
        std::unique_lock<std::mutex> lock(mCacheMutex);
        mFlushCondition.wait_for(lock, std::chrono::milliseconds(100), [this] {
            return !mPendingFaults.empty() || !mFlushThreadRunning;
        });

        if (!mFlushThreadRunning) {
            break;
        }

        if (mPendingFaults.empty()) {
            continue;
        }

        std::queue<FaultInfo> tempQueue;
        std::swap(tempQueue, mPendingFaults);
        lock.unlock();

        std::string filepath = getFaultFilePath();
        std::fstream file(filepath, std::ios::binary | std::ios::in | std::ios::out | std::ios::ate);
        
        if (!file) {
            file.open(filepath, std::ios::binary | std::ios::out);
            if (!file) {
                LOG_ERROR("flush loop: failed to open fault file: %s", filepath.c_str());
                continue;
            }
        }

        while (!tempQueue.empty()) {
            FaultInfo fault = tempQueue.front();
            tempQueue.pop();
            file.write((const char*)&fault, sizeof(fault));
        }
        file.close();
    }
}

bool FaultStorage::flush() {
    if (!mInitialized) {
        return false;
    }

    mFlushCondition.notify_one();

    std::this_thread::sleep_for(std::chrono::milliseconds(200));

    return true;
}

bool FaultStorage::loadFaults(std::vector<FaultInfo>& faults) {
    if (!mInitialized) {
        return false;
    }

    flush();

    std::string filepath = getFaultFilePath();
    std::ifstream file(filepath, std::ios::binary);
    if (!file) {
        return false;
    }

    file.seekg(0, std::ios::end);
    std::streampos size = file.tellg();
    file.seekg(0, std::ios::beg);

    size_t count = size / sizeof(FaultInfo);
    faults.resize(count);
    file.read((char*)faults.data(), size);
    file.close();

    return true;
}

bool FaultStorage::clearLowSeverityFaults() {
    if (!mInitialized) {
        return false;
    }

    flush();

    std::vector<FaultInfo> faults;
    if (!loadFaults(faults)) {
        return true;
    }

    auto it = std::remove_if(faults.begin(), faults.end(), [](const FaultInfo& f) {
        uint32_t severity = (f.fault_code >> 28) & 0x0F;
        return severity <= FAULT_SEVERITY_INFO;
    });
    faults.erase(it, faults.end());

    std::string filepath = getFaultFilePath();
    std::ofstream file(filepath, std::ios::binary | std::ios::trunc);
    if (!file) {
        return false;
    }

    file.write((const char*)faults.data(), faults.size() * sizeof(FaultInfo));
    file.close();

    return true;
}

bool FaultStorage::clearExpiredFaults(uint64_t max_age_ms) {
    if (!mInitialized) {
        return false;
    }

    flush();

    std::vector<FaultInfo> faults;
    if (!loadFaults(faults)) {
        return true;
    }

    uint64_t now = ClockCycles() / 1000;

    auto it = std::remove_if(faults.begin(), faults.end(), [max_age_ms, now](const FaultInfo& f) {
        uint64_t fault_time_ms = f.timestamp / 1000;
        return (now - fault_time_ms) > max_age_ms;
    });
    faults.erase(it, faults.end());

    std::string filepath = getFaultFilePath();
    std::ofstream file(filepath, std::ios::binary | std::ios::trunc);
    if (!file) {
        return false;
    }

    file.write((const char*)faults.data(), faults.size() * sizeof(FaultInfo));
    file.close();

    return true;
}

bool FaultStorage::clearAllFaults() {
    if (!mInitialized) {
        return false;
    }

    flush();

    std::string filepath = getFaultFilePath();
    std::ofstream file(filepath, std::ios::binary | std::ios::trunc);
    if (!file) {
        return false;
    }
    file.close();

    return true;
}

bool FaultStorage::removeFault(fault_code_t fault_code, uint64_t timestamp) {
    if (!mInitialized) {
        return false;
    }

    flush();

    std::vector<FaultInfo> faults;
    if (!loadFaults(faults)) {
        return true;
    }

    auto it = std::remove_if(faults.begin(), faults.end(), [fault_code, timestamp](const FaultInfo& f) {
        return f.fault_code == fault_code && f.timestamp == timestamp;
    });
    faults.erase(it, faults.end());

    std::string filepath = getFaultFilePath();
    std::ofstream file(filepath, std::ios::binary | std::ios::trunc);
    if (!file) {
        return false;
    }

    file.write((const char*)faults.data(), faults.size() * sizeof(FaultInfo));
    file.close();

    return true;
}

bool FaultStorage::wasNormalExit() {
    if (!mInitialized) {
        return false;
    }

    std::string marker_path = mStoragePath + "/exit_marker.dat";
    std::ifstream marker_file(marker_path);
    bool existed = marker_file.is_open();
    marker_file.close();

    if (existed) {
        remove(marker_path.c_str());
    }

    return existed;
}

void FaultStorage::markNormalExit() {
    if (!mInitialized) {
        return;
    }

    std::string marker_path = mStoragePath + "/exit_marker.dat";
    std::ofstream marker_file(marker_path);
    if (marker_file) {
        marker_file.close();
    }
}
