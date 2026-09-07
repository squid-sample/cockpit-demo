#ifndef __FAULT_STORAGE_H__
#define __FAULT_STORAGE_H__

#include "FaultCommon.h"
#include <vector>
#include <string>
#include <mutex>
#include <thread>
#include <atomic>
#include <condition_variable>
#include <queue>
#include <chrono>

class FaultStorage {
public:
    FaultStorage();
    ~FaultStorage();

    bool init(const std::string& path = "/persist/faults");
    void destroy();

    bool saveFault(const FaultInfo& fault_info);
    bool saveFaultSync(const FaultInfo& fault_info);
    bool flush();
    bool loadFaults(std::vector<FaultInfo>& faults);
    bool clearLowSeverityFaults();
    bool clearExpiredFaults(uint64_t max_age_ms);
    bool clearAllFaults();
    bool removeFault(fault_code_t fault_code, uint64_t timestamp);

    bool wasNormalExit();
    void markNormalExit();

private:
    std::string mStoragePath;
    bool mInitialized;

    std::queue<FaultInfo> mPendingFaults;
    std::mutex mCacheMutex;
    std::condition_variable mFlushCondition;
    std::thread mFlushThread;
    std::atomic<bool> mFlushThreadRunning;

    bool ensureDirectory();
    std::string getFaultFilePath();
    void flushLoop();
};

#endif