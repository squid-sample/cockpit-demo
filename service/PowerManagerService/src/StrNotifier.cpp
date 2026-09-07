#define LOG_TAG "PowerManagerService"
#include "log.h"

#include "StrNotifier.h"
#include <fcntl.h>
#include <unistd.h>
#include <string.h>

#ifdef __QNX__
#include <devctl.h>
#include <sys/dcmd_chr.h>
#endif

StrNotifier::StrNotifier(const char* pm_device, int pm_cmd)
    : mPmDevice(pm_device ? pm_device : DEFAULT_PM_DEVICE_PATH)
    , mPmCmd(pm_cmd)
    , mFd(-1)
    , mInitialized(false) {
}

StrNotifier::~StrNotifier() {
    destroy();
}

bool StrNotifier::init() {
#ifdef __QNX__
    mFd = open(mPmDevice.c_str(), O_RDWR);
    if (mFd < 0) {
        LOG_WARN("StrNotifier: cannot open %s, STR kernel notification inactive",
                 mPmDevice.c_str());
        mInitialized = false;
        return false;
    }

    mInitialized = true;
    LOG_INFO("StrNotifier initialized, pm_device=%s devctl_cmd=0x%x",
             mPmDevice.c_str(), mPmCmd);
#else
    mInitialized = false;
    LOG_WARN("StrNotifier: not on QNX, STR kernel notification inactive");
#endif
    return mInitialized;
}

void StrNotifier::destroy() {
    if (mFd >= 0) {
        close(mFd);
        mFd = -1;
    }
    mInitialized = false;
}

bool StrNotifier::notifyStr() {
    if (!mInitialized || mFd < 0) {
        LOG_WARN("StrNotifier not initialized, cannot trigger STR");
        return false;
    }

#ifdef __QNX__
    /* Send STR command to the platform PM driver via devctl */
    int ret = devctl(mFd, mPmCmd, NULL, 0, NULL);
    if (ret != EOK) {
        LOG_ERROR("StrNotifier: devctl(cmd=0x%x) on %s failed: %d",
                  mPmCmd, mPmDevice.c_str(), ret);
        return false;
    }

    LOG_INFO("StrNotifier: STR triggered via devctl on %s", mPmDevice.c_str());
    return true;
#else
    (void)mPmCmd;
    LOG_WARN("StrNotifier: devctl not available on this platform");
    return false;
#endif
}
