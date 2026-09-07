#define LOG_TAG "FaultCollector"
#include "log.h"

#include "FaultCollectorManager.h"
#include <iostream>
#include <vector>

FaultCollectorManager::FaultCollectorManager() {
}

FaultCollectorManager::~FaultCollectorManager() {
    stop();
}

bool FaultCollectorManager::init() {
    mCollector = std::make_unique<FaultCollector>();
    mAdapter = std::make_unique<FdbusAdapter>("com.cockpit.fault.qnx.service");
    mCache = std::make_unique<FaultCache>();
    mStorage = std::make_unique<FaultStorage>();

    if (!mCollector->init()) {
        LOG_ERROR("Failed to initialize FaultCollector");
        return false;
    }

    if (!mAdapter->init()) {
        LOG_ERROR("Failed to initialize FdbusAdapter");
        return false;
    }

    if (!mStorage->init()) {
        LOG_ERROR("Failed to initialize FaultStorage");
        return false;
    }

    mCollector->setFaultHandler(std::bind(&FaultCollectorManager::handleFault, this, std::placeholders::_1));
    mAdapter->setLinkUpHandler(std::bind(&FaultCollectorManager::retryUnconfirmedFaults, this));
    mAdapter->startTimer(30000, std::bind(&FaultCollectorManager::checkAndFlushCache, this));

    LOG_INFO("FaultCollectorManager initialized");

    if (!wasNormalExit()) {
        LOG_WARN("abnormal exit detected, reporting crash recovery");
        FaultInfo recovery_info;
        recovery_info.fault_code = FAULT_CODE_FC_CRASH_RECOVERY;
        recovery_info.timestamp = ClockCycles();
        recovery_info.status = FAULT_STATUS_PENDING;
        handleFault(recovery_info);
    }

    retryUnconfirmedFaults();

    return true;
}

void FaultCollectorManager::run() {
    if (mCollector) {
        mCollector->run();
    }
}

void FaultCollectorManager::stop() {
    flushCacheToStorage();

    if (mCollector) {
        mCollector->stop();
        mCollector.reset();
    }
    if (mAdapter) {
        mAdapter->destroy();
        mAdapter.reset();
    }
    if (mCache) {
        mCache.reset();
    }
    if (mStorage) {
        mStorage.reset();
    }
}

void FaultCollectorManager::handleFault(const FaultInfo& fault_info) {
    FaultInfo fault = fault_info;

    bool invoke_success = false;
    if (mAdapter) {
        invoke_success = mAdapter->invokeFault(fault, 5000);
    }

    if (!invoke_success) {
        LOG_WARN("fault invoke failed, caching: code=0x%08X", fault.fault_code);
        if (mCache) {
            if (mCache->isFull()) {
                flushCacheToStorage();
            }
            mCache->addFault(fault);
        }
    }
}

void FaultCollectorManager::checkAndFlushCache() {
    std::lock_guard<std::mutex> lock(mRetryMutex);

    if (mCache && mCache->getCount() > 0) {
        flushCacheToStorage();
    }
}

void FaultCollectorManager::flushCacheToStorage() {
    if (!mCache || !mStorage) {
        return;
    }

    std::vector<FaultInfo> faults;
    mCache->flush(faults);

    for (const auto& fault : faults) {
        mStorage->saveFaultSync(fault);
    }

    mCache->clear();
}

void FaultCollectorManager::retryUnconfirmedFaults() {
    std::lock_guard<std::mutex> lock(mRetryMutex);

    retryFromCache();
    retryFromStorage();
}

void FaultCollectorManager::retryFromCache() {
    if (!mCache || mCache->getCount() == 0) {
        return;
    }

    size_t count = mCache->getCount();
    for (size_t i = 0; i < count; i++) {
        FaultInfo fault;
        if (!mCache->getFault(i, fault)) {
            continue;
        }

        bool invoke_success = false;
        if (mAdapter) {
            invoke_success = mAdapter->invokeFault(fault, 5000);
        }

        if (invoke_success) {
            if (mCache) {
                mCache->removeFault(fault.fault_code);
                count--;
                i--;
            }
        }
    }
}

void FaultCollectorManager::retryFromStorage() {
    if (!mStorage) {
        return;
    }

    std::vector<FaultInfo> faults;
    if (!mStorage->loadFaults(faults)) {
        return;
    }

    for (const auto& fault : faults) {
        bool invoke_success = false;
        if (mAdapter) {
            invoke_success = mAdapter->invokeFault(fault, 5000);
        }

        if (invoke_success) {
            if (mStorage) {
                mStorage->removeFault(fault.fault_code, fault.timestamp);
            }
            if (mCache) {
                mCache->removeFault(fault.fault_code);
            }
        }
    }
}

bool FaultCollectorManager::wasNormalExit() {
    return (mStorage) ? mStorage->wasNormalExit() : false;
}

void FaultCollectorManager::markNormalExit() {
    flushCacheToStorage();
    if (mStorage) {
        mStorage->markNormalExit();
    }
}
