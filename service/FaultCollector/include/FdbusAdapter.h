#ifndef __FDBUS_ADAPTER_H__
#define __FDBUS_ADAPTER_H__

#include "FaultCommon.h"
#include <fdbus/CBaseServer.h>
#include <fdbus/CFdbContext.h>
#include <functional>

class FdbusAdapter : public ipc::fdbus::CBaseServer {
public:
    FdbusAdapter(const char* name);
    ~FdbusAdapter();

    bool init();
    void destroy();

    bool invokeFault(const FaultInfo& fault_info, int32_t timeout_ms = 5000);

    typedef std::function<void()> LinkUpHandler;
    void setLinkUpHandler(LinkUpHandler handler);

    bool isConnected();

    void startTimer(int32_t interval_ms, std::function<void()> callback);
    void stopTimer();

protected:
    void onOnline(ipc::fdbus::CFdbSession* session);
    void onOffline(ipc::fdbus::CFdbSession* session);
    void onTimer(int32_t timer_id);

private:
    bool mInitialized;
    ipc::fdbus::CFdbContext* mContext;
    ipc::fdbus::FdbSessionId_t mClientSid;
    LinkUpHandler mLinkUpHandler;
    int32_t mTimerId;
    std::function<void()> mTimerCallback;
};

#endif