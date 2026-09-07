#ifndef __FAULT_COLLECTOR_MANAGER_H__
#define __FAULT_COLLECTOR_MANAGER_H__

#include "FaultCommon.h"
#include "Singleton.h"
#include "FaultCollector.h"
#include "FdbusAdapter.h"
#include "FaultCache.h"
#include "FaultStorage.h"
#include <memory>
#include <mutex>

// class FaultCollector;
// class FdbusAdapter;
// class FaultCache;
// class FaultStorage;

class FaultCollectorManager {
public:
    bool init();
    void run();
    void stop();

    void handleFault(const FaultInfo& fault_info);
    bool wasNormalExit();
    void markNormalExit();

private:
    void retryUnconfirmedFaults();
    void retryFromCache();
    void retryFromStorage();
    void checkAndFlushCache();
    void flushCacheToStorage();
    FaultCollectorManager();
    ~FaultCollectorManager();

    std::unique_ptr<FaultCollector> mCollector;
    std::unique_ptr<FdbusAdapter> mAdapter;
    std::unique_ptr<FaultCache> mCache;
    std::unique_ptr<FaultStorage> mStorage;

    std::mutex mRetryMutex;

    DECLARE_SINGLETON_FRIEND(FaultCollectorManager)
};

#endif
