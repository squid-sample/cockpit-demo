#define LOG_TAG "PowerManagerService"
#include "log.h"

#include "EcdClient.h"
#include <fdbus/CFdbMessage.h>
#include <string.h>

using namespace ipc::fdbus;

EcdClient::EcdClient(const char* server_url)
    : CBaseClient("com.cockpit.power.ecd_client")
    , mServerUrl(server_url ? server_url : DEFAULT_ECD_SERVICE_URL)
    , mWorker(nullptr)
    , mInitialized(false) { 
    memset(&mCurrentMode, 0, sizeof(mCurrentMode));
}

EcdClient::~EcdClient() {
    destroy();
}

bool EcdClient::init() {
    if (!FDB_CONTEXT->start()) {
        LOG_ERROR("EcdClient: failed to start FDB context");
        return false;
    }

    mWorker = new ipc::fdbus::CBaseWorker();
    if (!mWorker || !mWorker->start()) {
        LOG_ERROR("EcdClient: failed to start worker");
        delete mWorker;
        mWorker = nullptr;
        return false;
    }

    ConnectStatus status = connect(mServerUrl.c_str()); 
    if (status != CONNECTED) {
        LOG_ERROR("EcdClient: connect to %s failed, status=%d",
                  mServerUrl.c_str(), (int)status);
    } else {
        LOG_INFO("EcdClient: connected to ECDService at %s", mServerUrl.c_str());
    }

    mInitialized = true;
    return true;
}

void EcdClient::destroy() {
    if (!mInitialized) {
        return;
    }

    prepareDestroy();
    disconnect();

    if (mWorker) {
        mWorker->exit();
        mWorker->join();
        delete mWorker;
        mWorker = nullptr;
    }

    mInitialized = false;
}

void EcdClient::setPowerModeHandler(PowerModeHandler handler) {
    mHandler = handler;
}

void EcdClient::onOnline(const ipc::fdbus::CFdbOnlineInfo &info) {
    CBaseClient::onOnline(info);
    LOG_INFO("EcdClient: connected to ECDService, sid=%lu",
             (unsigned long)info.mSid);

    ipc::fdbus::CFdbMsgSubscribeList sub_list;
    sub_list.addNotifyItem(FDB_MSG_ECD_POWER_STATE);
    if (!subscribe(sub_list)) {
        LOG_ERROR("EcdClient: subscribe FDB_MSG_ECD_POWER_STATE failed");
    } else {
        LOG_INFO("EcdClient: subscribed to ECD power state broadcast");
    }
}

void EcdClient::onOffline(const ipc::fdbus::CFdbOnlineInfo &info) {
    CBaseClient::onOffline(info);
    LOG_WARN("EcdClient: ECDService disconnected, sid=%lu",
             (unsigned long)info.mSid);
}

void EcdClient::onBroadcast(CBaseJob::Ptr &msg_ref) {
    auto* msg = castToMessage<CFdbMessage *>(msg_ref);
    if (!msg) {
        return;
    }

    if (msg->code() != FDB_MSG_ECD_POWER_STATE) {
        return;
    }

    int32_t payload_size = msg->getPayloadSize();
    auto* data = (const PowerModeInfo*)msg->getPayloadBuffer();
    if (!data || payload_size < (int32_t)sizeof(PowerModeInfo)) {
        LOG_WARN("EcdClient: invalid payload size=%d, expected=%d",
                 payload_size, (int32_t)sizeof(PowerModeInfo));
        return;
    }

    PowerModeInfo new_mode = *data;

    if ((uint32_t)new_mode.mode > POWER_MODE_DEEP_SLEEP) {
        LOG_ERROR("EcdClient: invalid power mode %u from ECDService",
                  (unsigned)new_mode.mode);
        return;
    }

    if (new_mode.mode == mCurrentMode.mode) {
        return;
    }

    LOG_INFO("EcdClient: power mode %d -> %d",
             (int)mCurrentMode.mode, (int)new_mode.mode);
    mCurrentMode = new_mode;

    if (mHandler) {
        mHandler(new_mode);
    }
}
