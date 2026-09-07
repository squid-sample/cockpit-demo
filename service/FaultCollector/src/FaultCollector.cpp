#define LOG_TAG "FaultCollector"
#include "log.h"

#include "FaultCollector.h"
#include <sys/neutrino.h>
#include <sys/dispatch.h>
#include <unistd.h>
#include <iostream>
#include <ha/ham.h>

FaultCollector::FaultCollector()
    : mChId(-1), mNsId(-1), mRunning(false) {
}

FaultCollector::~FaultCollector() {
    destroy();
}

bool FaultCollector::init() {
    mChId = ChannelCreate(0);
    if (mChId < 0) {
        LOG_ERROR("Failed to create channel");
        return false;
    }

    mNsId = name_attach(mChId, FAULT_SERVICE_NAME, 0);
    if (mNsId < 0) {
        LOG_ERROR("Failed to name_attach: %s", FAULT_SERVICE_NAME);
        ChannelDestroy(mChId);
        mChId = -1;
        return false;
    }

    if (!initHamMonitoring()) {
        LOG_WARN("Failed to init HAM monitoring, running without HAM");
    }

    mRunning = true;
    return true;
}

void FaultCollector::destroy() {
    mRunning = false;

    cleanupHamMonitoring();

    if (mNsId >= 0) {
        name_detach(mNsId, 0);
        mNsId = -1;
    }

    if (mChId >= 0) {
        ChannelDestroy(mChId);
        mChId = -1;
    }
}

void FaultCollector::run() {
    if (!mRunning) {
        return;
    }

    FaultMessage msg;
    while (mRunning) {
        int rcvid = MsgReceive(mChId, &msg, sizeof(msg), NULL);
        if (rcvid < 0) {
            continue;
        }

        if (rcvid == 0) {
            handlePulse(rcvid, &msg.pulse);
        } else {
            handleMessage(rcvid, &msg);
        }
    }
}

void FaultCollector::stop() {
    mRunning = false;
}

void FaultCollector::setFaultHandler(FaultHandler handler) {
    mFaultHandler = handler;
}

void FaultCollector::handleMessage(int rcvid, const FaultMessage* msg) {
    FaultReply reply;
    reply.status = 0;

    switch (msg->type) {
        case MSG_TYPE_REPORT_SYNC: {
            int ret = deduplicate(msg->fault_info.fault_code);
            if (ret == 0) {
                processFault(msg->fault_info, msg->message);
            } else {
                reply.status = ret;
            }
            break;
        }
        case MSG_TYPE_REPORT_ASYNC: {
            int ret = deduplicate(msg->fault_info.fault_code);
            if (ret == 0) {
                processFault(msg->fault_info, msg->message);
            }
            break;
        }
        default:
            LOG_WARN("unknown message type: %u", msg->type);
            reply.status = -1;
            break;
    }

    MsgReply(rcvid, EOK, &reply, sizeof(reply));
}

void FaultCollector::handlePulse(int rcvid, const struct _pulse* pulse) {
    (void)rcvid;
    handleHamPulse(pulse->code, pulse->value.sival_int);
}

void FaultCollector::handleHamPulse(int code, int value) {
    FaultInfo fault_info;
    fault_info.timestamp = ClockCycles();
    std::string msg;

    switch (code) {
        case PULSE_CODE_HAM_PROCESS_CRASH: {
            fault_info.fault_code = FAULT_CODE_HAM_PROCESS_CRASH;
            msg = "Process crash detected, pid=" + std::to_string(value);
            LOG_ERROR("HAM: process crash, pid=%d", value);
            break;
        }
        case PULSE_CODE_HAM_WATCHDOG_TIMEOUT: {
            fault_info.fault_code = FAULT_CODE_HAM_WATCHDOG_TIMEOUT;
            msg = "Watchdog timeout, pid=" + std::to_string(value);
            LOG_ERROR("HAM: watchdog timeout, pid=%d", value);
            break;
        }
        case PULSE_CODE_HAM_RESOURCE_EXHAUSTED: {
            fault_info.fault_code = FAULT_CODE_HAM_RESOURCE_EXHAUSTED;
            msg = "Resource exhausted, type=" + std::to_string(value);
            LOG_ERROR("HAM: resource exhausted, type=%d", value);
            break;
        }
        case PULSE_CODE_HAM_PROCESS_EXIT: {
            fault_info.fault_code = FAULT_CODE_HAM_PROCESS_CRASH;
            msg = "Process abnormal exit, pid=" + std::to_string(value);
            LOG_WARN("HAM: process abnormal exit, pid=%d", value);
            break;
        }
        default:
            LOG_WARN("HAM: unknown pulse code: %d", code);
            return;
    }

    processFault(fault_info, msg);
}

void FaultCollector::processFault(const FaultInfo& fault_info, const std::string& msg) {
    if (mFaultHandler) {
        mFaultHandler(fault_info);
    }
}

int FaultCollector::deduplicate(fault_code_t fault_code) {
    uint64_t now = ClockCycles();
    uint64_t interval_cycles = (uint64_t)DEDUP_INTERVAL_MS * (uint64_t)ClockCyclesPerSec() / 1000;

    if (mFaultDedupMap.size() >= DEDUP_CLEANUP_THRESHOLD) {
        uint64_t cleanup_cycles = (uint64_t)DEDUP_CLEANUP_AGE_MS * (uint64_t)ClockCyclesPerSec() / 1000;
        cleanupExpiredEntries(now, cleanup_cycles);
    }

    auto it = mFaultDedupMap.find(fault_code);
    if (it != mFaultDedupMap.end()) {
        uint64_t delta = now - it->second.last_report_time;
        if (delta < interval_cycles) {
            it->second.count++;
            return -5;
        }
    }

    mFaultDedupMap[fault_code] = {now, 1};
    return 0;
}

void FaultCollector::cleanupExpiredEntries(uint64_t now, uint64_t max_age_cycles) {
    for (auto it = mFaultDedupMap.begin(); it != mFaultDedupMap.end(); ) {
        uint64_t delta = now - it->second.last_report_time;
        if (delta > max_age_cycles) {
            it = mFaultDedupMap.erase(it);
        } else {
            ++it;
        }
    }
}

bool FaultCollector::initHamMonitoring() {
    int rc = ham_connect(0);
    if (rc != 0) {
        LOG_ERROR("ham_connect failed");
        return false;
    }

    ham_entity_t* entity = ham_attach("FaultCollector", 0, getpid(), NULL, 0);
    if (entity == NULL) {
        LOG_ERROR("ham_attach failed");
        ham_disconnect();
        return false;
    }

    ham_condition_t* cond = ham_condition(entity, HCOND_DEATH, "death", 0);
    if (cond == NULL) {
        LOG_ERROR("ham_condition failed");
        ham_detach(entity);
        ham_disconnect();
        return false;
    }

    ham_action_notify_pulse(cond, "notify", mChId, 0, PULSE_CODE_HAM_PROCESS_CRASH, 0);
    ham_action_restart(cond, "restart", "/path/to/FaultCollector.qnx", 0);

    return true;
}

void FaultCollector::cleanupHamMonitoring() {
    ham_disconnect();
}