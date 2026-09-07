#ifndef __FDBUS_POWER_ADAPTER_H__
#define __FDBUS_POWER_ADAPTER_H__

#include "PowerManagerCommon.h"
#include <fdbus/CBaseServer.h>
#include <fdbus/CBaseJob.h>
#include <fdbus/CFdbContext.h>
#include <fdbus/CBaseWorker.h>
#include <functional>
#include <memory>
#include <string>
#include <set>

/*
 * Link 2: Other (non-STR) power modes -> fdbus broadcast -> Android native client
 *
 * The FdbusPowerAdapter acts as an fdbus server. Android native clients
 * subscribe to FDB_MSG_POWER_MODE_BROADCAST events. When a non-STR power
 * mode arrives from MCU, the manager calls broadcastPowerMode(), which
 * broadcasts the PowerModeInfo struct to all connected subscribers.
 *
 * The adapter also supports onSubscribe() so that a newly connected client
 * immediately receives the current power mode (event caching is enabled via
 * initEventCache()).
 */
class FdbusPowerAdapter : public ipc::fdbus::CBaseServer {
public:
    /* tcp_url: if non-null, bind via TCP direct connection; if null, use name server */
    FdbusPowerAdapter(const char* name, const char* tcp_url = nullptr);
    ~FdbusPowerAdapter();

    bool init();
    void destroy();

    /* Broadcast power mode to all subscribed Android clients */
    bool broadcastPowerMode(const PowerModeInfo& power_info);

    /* Set the current power mode (used for event cache / late subscriber push) */
    void setCurrentPowerMode(const PowerModeInfo& power_info);

    typedef std::function<void()> LinkUpHandler;
    void setLinkUpHandler(LinkUpHandler handler);

    bool isConnected();

protected:
    /* Called when a client subscribes to an event */
    void onSubscribe(ipc::fdbus::CBaseJob::Ptr &msg_ref) override;

    /* Called when a client connects */
    void onOnline(const ipc::fdbus::CFdbOnlineInfo &info) override;

    /* Called when a client disconnects */
    void onOffline(const ipc::fdbus::CFdbOnlineInfo &info) override;

private:
    bool mInitialized;
    std::string mTcpUrl;
    ipc::fdbus::CBaseWorker* mWorker;
    std::set<FdbSessionId_t> mClientSids;  /* track ALL connected clients */
    LinkUpHandler mLinkUpHandler;
    PowerModeInfo mCurrentMode;
};

#endif
