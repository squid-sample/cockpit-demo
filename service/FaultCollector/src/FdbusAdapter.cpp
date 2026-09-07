#define LOG_TAG "FaultCollector"
#include "log.h"

#include "FdbusAdapter.h"
#include <fdbus/CFdbRawMsgBuilder.h>
#include <fdbus/CBaseMessage.h>

FdbusAdapter::FdbusAdapter(const char* name)
    : CBaseServer(name, NULL, NULL), mInitialized(false), mContext(NULL), mClientSid(FDB_INVALID_ID), mTimerId(-1) {
}

FdbusAdapter::~FdbusAdapter() {
    destroy();
}

bool FdbusAdapter::init() {
    mContext = ipc::fdbus::CFdbContext::getInstance();
    if (!mContext) {
        LOG_ERROR("failed to get FdbContext");
        return false;
    }

    ipc::fdbus::CFdbContext::init();
    
    enableUDP(true);
    
    if (!start()) {
        LOG_ERROR("failed to start FdbusServer");
        return false;
    }

    mInitialized = true;
    return true;
}

void FdbusAdapter::destroy() {
    if (mInitialized) {
        stop();
        mInitialized = false;
    }
}

bool FdbusAdapter::invokeFault(const FaultInfo& fault_info, int32_t timeout_ms) {
    if (!mInitialized) {
        return false;
    }

    if (mClientSid == FDB_INVALID_ID) {
        LOG_WARN("invoke failed: no client connected, code=0x%08X", fault_info.fault_code);
        return false;
    }

    ipc::fdbus::CFdbRawMsgBuilder builder;
    builder.beginMessage(0, 0, 0);
    builder.addPayload((const uint8_t*)&fault_info, sizeof(fault_info));
    builder.endMessage();

    CBaseJob::Ptr msg_ref(new CBaseMessage(0));
    bool success = invoke(mClientSid, msg_ref, builder, timeout_ms);

    if (!success) {
        LOG_WARN("invoke failed: code=0x%08X, timeout=%dms", fault_info.fault_code, timeout_ms);
    }

    return success;
}

void FdbusAdapter::setLinkUpHandler(LinkUpHandler handler) {
    mLinkUpHandler = handler;
}

bool FdbusAdapter::isConnected() {
    return (mInitialized && mClientSid != FDB_INVALID_ID);
}

void FdbusAdapter::onOnline(ipc::fdbus::CFdbSession* session) {
    CBaseServer::onOnline(session);
    mClientSid = session->sid();

    if (mLinkUpHandler) {
        mLinkUpHandler();
    }
}

void FdbusAdapter::onOffline(ipc::fdbus::CFdbSession* session) {
    CBaseServer::onOffline(session);
    if (mClientSid == session->sid()) {
        LOG_WARN("client disconnected, sid=%lu", (unsigned long)mClientSid);
        mClientSid = FDB_INVALID_ID;
    }
}

void FdbusAdapter::startTimer(int32_t interval_ms, std::function<void()> callback) {
    if (!mInitialized) {
        return;
    }

    stopTimer();

    mTimerCallback = callback;
    mTimerId = mContext->addTimer(interval_ms, this);
}

void FdbusAdapter::stopTimer() {
    if (mTimerId >= 0 && mContext) {
        mContext->removeTimer(mTimerId);
        mTimerId = -1;
    }
}

void FdbusAdapter::onTimer(int32_t timer_id) {
    if (timer_id == mTimerId && mTimerCallback) {
        mTimerCallback();
    }
}