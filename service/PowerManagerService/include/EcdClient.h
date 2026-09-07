#ifndef __ECD_CLIENT_H__
#define __ECD_CLIENT_H__

#include "PowerManagerCommon.h"
#include <fdbus/CBaseClient.h>
#include <fdbus/CBaseJob.h>
#include <fdbus/CFdbContext.h>
#include <fdbus/CBaseWorker.h>
#include <functional>
#include <string>

/*
 * EcdClient: fdbus client subscribing to ECDService for MCU power state.
 *
 * Data path:
 *   MCU --SPI--> QNX SPI driver --> ECDService (fdbus server)
 *                                       | broadcast FDB_MSG_ECD_POWER_STATE
 *                                       v
 *                                 EcdClient (fdbus client, this class)
 *                                       | onBroadcast callback
 *                                       v
 *                                 PowerManager::handlePowerMode
 *
 * ECDService is the central gateway for all MCU data. It publishes decoded
 * power state as a PowerModeInfo struct via fdbus broadcast. EcdClient
 * connects to ECDService, subscribes, and forwards received states to the
 * PowerManager through the PowerModeHandler callback.
 */
class EcdClient : public ipc::fdbus::CBaseClient {
public:
    typedef std::function<bool(const PowerModeInfo&)> PowerModeHandler;

    EcdClient(const char* server_url = DEFAULT_ECD_SERVICE_URL);
    ~EcdClient();

    bool init();
    void destroy();

    void setPowerModeHandler(PowerModeHandler handler);
    PowerModeInfo getCurrentMode() const { return mCurrentMode; }

protected:
    void onOnline(const ipc::fdbus::CFdbOnlineInfo &info) override;
    void onOffline(const ipc::fdbus::CFdbOnlineInfo &info) override;
    void onBroadcast(ipc::fdbus::CBaseJob::Ptr &msg_ref) override;

private:
    std::string mServerUrl;
    ipc::fdbus::CBaseWorker* mWorker;
    PowerModeHandler mHandler;
    PowerModeInfo mCurrentMode;
    bool mInitialized;
};

#endif
