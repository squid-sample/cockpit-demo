#ifndef __FAULT_CACHE_H__
#define __FAULT_CACHE_H__

#include "FaultCommon.h"
#include <vector>

#define MAX_CACHE_SIZE 256

class FaultCache {
public:
    FaultCache();
    ~FaultCache();

    void addFault(const FaultInfo& fault_info);
    bool getFault(size_t index, FaultInfo& fault_info);
    size_t getCount();
    bool isFull();
    void flush(std::vector<FaultInfo>& faults);
    void clear();
    bool removeFault(fault_code_t fault_code);

private:
    FaultInfo mCache[MAX_CACHE_SIZE];
    size_t mHead;
    size_t mTail;
    size_t mCount;
};

#endif