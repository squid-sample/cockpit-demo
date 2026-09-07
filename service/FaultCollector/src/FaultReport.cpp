#include "FaultReport.h"
#include <sys/neutrino.h>
#include <sys/dispatch.h>
#include <errno.h>
#include <unistd.h>

FaultReport::FaultReport() : mCoId(-1), mConnected(false) {
}

FaultReport::~FaultReport() {
    destroy();
}

bool FaultReport::init() {
    return connectToService();
}

void FaultReport::destroy() {
    disconnect();
}

int FaultReport::report(fault_code_t fault_code, const std::string& msg, bool is_recover) {
    if (!isConnected() && !connectToService()) {
        return -2;
    }

    FaultMessage fault_msg;
    fault_msg.type = MSG_TYPE_REPORT_SYNC;
    fault_msg.fault_info.fault_code = fault_code;
    fault_msg.fault_info.timestamp = ClockCycles();
    
    if (msg.length() < sizeof(fault_msg.message)) {
        msg.copy(fault_msg.message, msg.length());
        fault_msg.message[msg.length()] = '\0';
    } else {
        msg.copy(fault_msg.message, sizeof(fault_msg.message) - 1);
        fault_msg.message[sizeof(fault_msg.message) - 1] = '\0';
    }

    FaultReply reply;
    int rc = MsgSend(mCoId, &fault_msg, sizeof(fault_msg), &reply, sizeof(reply));
    if (rc != EOK) {
        disconnect();
        return -2;
    }

    return reply.status;
}

int FaultReport::reportAsync(fault_code_t fault_code, const std::string& msg, bool is_recover) {
    if (!isConnected() && !connectToService()) {
        return -2;
    }

    FaultMessage fault_msg;
    fault_msg.type = MSG_TYPE_REPORT_ASYNC;
    fault_msg.fault_info.fault_code = fault_code;
    fault_msg.fault_info.timestamp = ClockCycles();
    
    if (msg.length() < sizeof(fault_msg.message)) {
        msg.copy(fault_msg.message, msg.length());
        fault_msg.message[msg.length()] = '\0';
    } else {
        msg.copy(fault_msg.message, sizeof(fault_msg.message) - 1);
        fault_msg.message[sizeof(fault_msg.message) - 1] = '\0';
    }

    int rc = MsgSendPulse(mCoId, -1, MSG_TYPE_REPORT_ASYNC, fault_code);
    if (rc != EOK) {
        disconnect();
        return -2;
    }

    return 0;
}

bool FaultReport::isConnected() const {
    return mConnected && mCoId >= 0;
}

bool FaultReport::connectToService() {
    if (mConnected) {
        return true;
    }

    int retry = 10;
    while (retry--) {
        mCoId = name_open(FAULT_SERVICE_NAME, 0);
        if (mCoId >= 0) {
            mConnected = true;
            return true;
        }
        usleep(100000);
    }

    return false;
}

void FaultReport::disconnect() {
    if (mCoId >= 0) {
        name_close(mCoId);
        mCoId = -1;
    }
    mConnected = false;
}