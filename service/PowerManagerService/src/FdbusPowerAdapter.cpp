#define LOG_TAG "PowerManagerService"
#include "log.h"

#include "FdbusPowerAdapter.h"
#include <fdbus/CFdbMessage.h>
#include <string.h>

using namespace ipc::fdbus;

FdbusPowerAdapter::FdbusPowerAdapter(const char* name, const char* tcp_url)
    : CBaseServer(name)
    , mInitialized(false)
    , mTcpUrl(tcp_url ? tcp_url : "")
    , mWorker(nullptr) {
    memset(&mCurrentMode, 0, sizeof(mCurrentMode));
}

FdbusPowerAdapter::~FdbusPowerAdapter() {
    destroy();
}

bool FdbusPowerAdapter::init() {
    /* Start fdbus context (async, runs in background thread) */
    if (!FDB_CONTEXT->start()) {
        LOG_ERROR("Failed to start FDB context");
        return false;
    }

    enableUDP(true);

    /* Bind server: TCP direct connection (no nameserver required) */
    if (mTcpUrl.empty()) {
        LOG_ERROR("TCP url not configured");
        return false;
    }
    FdbSocketId_t skid = bind(mTcpUrl.c_str());
    if (skid == FDB_INVALID_ID) {
        LOG_ERROR("Failed to bind TCP: %s", mTcpUrl.c_str());
        return false;
    }
    LOG_INFO("FdbusPowerAdapter bound to %s", mTcpUrl.c_str());

    /* Create a worker for event scheduling */
    mWorker = new ipc::fdbus::CBaseWorker();
    if (!mWorker || !mWorker->start()) {
        LOG_ERROR("Failed to start worker");
        delete mWorker;
        mWorker = nullptr;
        return false;
    }

    /* Enable event cache so late subscribers can receive the last known state */
    enableEventCache(true);

    mInitialized = true;
    return true;
}

void FdbusPowerAdapter::destroy() {
    if (!mInitialized) {
        return;
    }

    prepareDestroy();
    unbind();

    if (mWorker) {
        mWorker->exit();
        mWorker->join();
        delete mWorker;
        mWorker = nullptr;
    }

    mInitialized = false;
}

bool FdbusPowerAdapter::broadcastPowerMode(const PowerModeInfo& power_info) {
    if (!mInitialized) {
        return false;
    }

    /* Keep member in sync so onSubscribe() can always send the latest mode */
    mCurrentMode = power_info;

    bool success = broadcast(FDB_MSG_POWER_MODE_BROADCAST,
                             (const void*)&power_info,
                             sizeof(power_info));

    if (!success) {
        LOG_WARN("broadcastPowerMode failed: mode=%d", (int)power_info.mode);
    } else {
        LOG_INFO("broadcastPowerMode: mode=%d, subscriber_count=%zu",
                 (int)power_info.mode, mClientSids.size());
    }

    return success;
}

void FdbusPowerAdapter::setCurrentPowerMode(const PowerModeInfo& power_info) {
    mCurrentMode = power_info;
    /* Pre-populate the event cache so subscribers connecting before the first
     * broadcast still receive a valid initial state. */
    if (mInitialized) {
        initEventCache(FDB_MSG_POWER_MODE_BROADCAST, "",
                       (const void*)&mCurrentMode, sizeof(mCurrentMode),
                       false, true);
    }
}

void FdbusPowerAdapter::setLinkUpHandler(LinkUpHandler handler) {
    mLinkUpHandler = handler;
}

bool FdbusPowerAdapter::isConnected() {
    return (mInitialized && !mClientSids.empty());
}

void FdbusPowerAdapter::onSubscribe(CBaseJob::Ptr &msg_ref) {
    auto* msg = castToMessage<CFdbMessage *>(msg_ref);
    if (!msg) {
        return;
    }

    FdbMsgCode_t msg_code = msg->code();
    if (msg_code == FDB_MSG_POWER_MODE_BROADCAST) {
        /* Send the current power mode to the newly subscribed client */
        broadcast(msg->session(),
                  FDB_MSG_POWER_MODE_BROADCAST,
                  (const void*)&mCurrentMode,
                  sizeof(mCurrentMode));
        LOG_INFO("onSubscribe: sent current mode=%d to new subscriber sid=%lu",
                 (int)mCurrentMode.mode, (unsigned long)msg->session());
    }
}

void FdbusPowerAdapter::onOnline(const ipc::fdbus::CFdbOnlineInfo &info) {
    CBaseServer::onOnline(info);
    bool was_empty = mClientSids.empty();
    mClientSids.insert(info.mSid);
    LOG_INFO("client connected, sid=%lu, total_clients=%zu",
             (unsigned long)info.mSid, mClientSids.size());

    /* Fire link-up handler the first time any client goes online */
    if (was_empty && mLinkUpHandler) {
        mLinkUpHandler();
    }
}

void FdbusPowerAdapter::onOffline(const ipc::fdbus::CFdbOnlineInfo &info) {
    CBaseServer::onOffline(info);
    size_t erased = mClientSids.erase(info.mSid);
    if (erased > 0) {
        LOG_WARN("client disconnected, sid=%lu, remaining=%zu",
                 (unsigned long)info.mSid, mClientSids.size());
    }
}
