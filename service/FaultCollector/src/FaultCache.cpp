#define LOG_TAG "FaultCollector"
#include "log.h"

#include "FaultCache.h"

FaultCache::FaultCache() : mHead(0), mTail(0), mCount(0) {
}

FaultCache::~FaultCache() {
}

void FaultCache::addFault(const FaultInfo& fault_info) {
    mCache[mHead] = fault_info;
    mHead = (mHead + 1) % MAX_CACHE_SIZE;

    if (mCount < MAX_CACHE_SIZE) {
        mCount++;
    } else {
        mTail = (mTail + 1) % MAX_CACHE_SIZE;
    }
}

bool FaultCache::getFault(size_t index, FaultInfo& fault_info) {
    if (index >= mCount) {
        return false;
    }

    size_t pos = (mTail + index) % MAX_CACHE_SIZE;
    fault_info = mCache[pos];
    return true;
}

size_t FaultCache::getCount() {
    return mCount;
}

bool FaultCache::isFull() {
    return (mCount >= MAX_CACHE_SIZE);
}

void FaultCache::flush(std::vector<FaultInfo>& faults) {
    faults.clear();
    for (size_t i = 0; i < mCount; i++) {
        FaultInfo fault;
        if (getFault(i, fault)) {
            faults.push_back(fault);
        }
    }
}

void FaultCache::clear() {
    mHead = 0;
    mTail = 0;
    mCount = 0;
}

bool FaultCache::removeFault(fault_code_t fault_code) {
    if (mCount == 0) {
        return false;
    }

    size_t found = MAX_CACHE_SIZE;
    for (size_t i = 0; i < mCount; i++) {
        size_t pos = (mTail + i) % MAX_CACHE_SIZE;
        if (mCache[pos].fault_code == fault_code) {
            found = pos;
            break;
        }
    }

    if (found == MAX_CACHE_SIZE) {
        return false;
    }

    for (size_t i = found; i != mHead; i = (i + 1) % MAX_CACHE_SIZE) {
        size_t next = (i + 1) % MAX_CACHE_SIZE;
        mCache[i] = mCache[next];
        if (next == mHead) {
            break;
        }
    }

    mHead = (mHead + MAX_CACHE_SIZE - 1) % MAX_CACHE_SIZE;
    mCount--;

    return true;
}