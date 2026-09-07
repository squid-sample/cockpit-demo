#ifndef __STR_NOTIFIER_H__
#define __STR_NOTIFIER_H__

#include "PowerManagerCommon.h"
#include <string>

/*
 * Notifies the kernel to enter the STR (Suspend-to-RAM) flow.
 *
 * QNX Neutrino does NOT have a Linux-style /sys/power/state sysfs interface.
 * On the 8295 Hypervisor, STR is triggered through the platform PM driver,
 * which exposes a /dev/ node controlled via devctl(). The exact device path
 * and devctl command code are platform-specific and configurable at runtime.
 *
 * If no PM driver node is available, init() returns false (non-fatal) and
 * the service continues operating with the other forwarding links.
 */
class StrNotifier {
public:
    StrNotifier(const char* pm_device = DEFAULT_PM_DEVICE_PATH,
                int pm_cmd = DEFAULT_PM_STR_CMD);
    ~StrNotifier();

    bool init();
    void destroy();

    /* Trigger the kernel STR flow via devctl to the PM driver */
    bool notifyStr();

private:
    std::string mPmDevice;
    int mPmCmd;
    int mFd;
    bool mInitialized;
};

#endif
