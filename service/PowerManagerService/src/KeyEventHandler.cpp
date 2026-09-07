#define LOG_TAG "PowerManagerService"
#include "log.h"

#include "KeyEventHandler.h"
#include <fcntl.h>
#include <unistd.h>
#include <string.h>
#include <time.h>

#ifdef __QNX__
#include <sys/neutrino.h>
#endif

/*
 * Linux input_event layout (compatible with Android input framework):
 *   struct input_event {
 *       struct timeval time;   // 16 bytes on 64-bit, 8 bytes on 32-bit
 *       uint16_t type;
 *       uint16_t code;
 *       int32_t  value;
 *   };
 *
 * Since we are building for QNX x86_64, the 64-bit layout is used.
 * timeval on QNX64: tv_sec (long, 8 bytes) + tv_usec (long, 8 bytes) = 16 bytes.
 * Total struct size: 16 + 2 + 2 + 4 = 24 bytes.
 */
struct input_event_t {
    int64_t  tv_sec;    /* compatible with struct timeval on 64-bit */
    int64_t  tv_usec;
    uint16_t type;
    uint16_t code;
    int32_t  value;
};

KeyEventHandler::KeyEventHandler(const char* device_path)
    : mDevicePath(device_path ? device_path : DEFAULT_KEYEVENT_DEVICE)
    , mFd(-1)
    , mInitialized(false) {
}

KeyEventHandler::~KeyEventHandler() {
    destroy();
}

bool KeyEventHandler::init() {
#ifdef __QNX__
    mFd = open(mDevicePath.c_str(), O_WRONLY);
#else
    /* On host (MinGW), /dev/input is not available; skip in simulation */
    mFd = open(mDevicePath.c_str(), O_WRONLY | O_BINARY);
#endif
    if (mFd < 0) {
        LOG_WARN("KeyEventHandler: failed to open %s, keyevent link inactive",
                 mDevicePath.c_str());
        /* Not fatal: the service can still operate the fdbus link */
        mInitialized = false;
        return false;
    }

    mInitialized = true;
    LOG_INFO("KeyEventHandler initialized on %s", mDevicePath.c_str());
    return true;
}

void KeyEventHandler::destroy() {
    if (mFd >= 0) {
        close(mFd);
        mFd = -1;
    }
    mInitialized = false;
}

bool KeyEventHandler::writeKeyEvent(uint16_t type, uint16_t code, int32_t value) {
    if (!mInitialized || mFd < 0) {
        LOG_WARN("KeyEventHandler not initialized, cannot send key event");
        return false;
    }

    struct input_event_t ev;
    memset(&ev, 0, sizeof(ev));

    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    ev.tv_sec  = (int64_t)ts.tv_sec;
    ev.tv_usec = (int64_t)(ts.tv_nsec / 1000);

    ev.type  = type;
    ev.code  = code;
    ev.value = value;

    ssize_t written = write(mFd, &ev, sizeof(ev));
    if (written != (ssize_t)sizeof(ev)) {
        LOG_ERROR("KeyEventHandler: write failed, ret=%zd, errno=%d",
                  written, errno);
        return false;
    }

    return true;
}

bool KeyEventHandler::sendKeyEvent(uint16_t type, uint16_t code, int32_t value) {
    return writeKeyEvent(type, code, value);
}

bool KeyEventHandler::sendPowerKey() {
    LOG_INFO("KeyEventHandler: injecting KEY_POWER press+release for STR");

    bool ok = true;
    ok &= writeKeyEvent(EV_KEY, KEY_POWER, 1);   /* press   */
    ok &= writeKeyEvent(EV_SYN, SYN_REPORT, 0);  /* sync after press */
    ok &= writeKeyEvent(EV_KEY, KEY_POWER, 0);   /* release */
    ok &= writeKeyEvent(EV_SYN, SYN_REPORT, 0);  /* sync after release */

    if (!ok) {
        LOG_ERROR("KeyEventHandler: failed to inject KEY_POWER");
    }

    return ok;
}
