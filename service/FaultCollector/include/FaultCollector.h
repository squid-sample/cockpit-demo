#ifndef __FAULT_COLLECTOR_H__
#define __FAULT_COLLECTOR_H__

#include "FaultCommon.h"
#include <string>
#include <functional>
#include <map>

#define DEDUP_INTERVAL_MS 1000
#define DEDUP_CLEANUP_THRESHOLD 100
#define DEDUP_CLEANUP_AGE_MS 10000

struct FaultDedupInfo {
    uint64_t last_report_time;
    int count;
};

class FaultCollector {
public:
    typedef std::function<void(const FaultInfo&)> FaultHandler;

    FaultCollector();
    ~FaultCollector();

    bool init();
    void destroy();

    void run();
    void stop();

    void setFaultHandler(FaultHandler handler);

private:
    void handleMessage(int rcvid, const FaultMessage* msg);
    void handlePulse(int rcvid, const struct _pulse* pulse);
    void processFault(const FaultInfo& fault_info, const std::string& msg);
    int deduplicate(fault_code_t fault_code);
    void cleanupExpiredEntries(uint64_t now, uint64_t max_age_cycles);
    void handleHamPulse(int code, int value);
    bool initHamMonitoring();
    void cleanupHamMonitoring();

    int mChId;
    int mNsId;
    bool mRunning;
    FaultHandler mFaultHandler;
    
    std::map<fault_code_t, FaultDedupInfo> mFaultDedupMap;
};

#endif