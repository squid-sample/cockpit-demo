#ifndef __KEY_EVENT_HANDLER_H__
#define __KEY_EVENT_HANDLER_H__

#include "PowerManagerCommon.h"
#include <string>

/*
 * Link 1: STR state -> keyevent -> Android
 *
 * On the Qualcomm 8295 Hypervisor, QNX injects key events into the Android
 * guest VM through the virtual input device framework. Writing Linux
 * input_event structures to the virtual input device node makes the events
 * appear at /dev/input/eventX on the Android side, where the Android
 * InputReader / PowerManager picks them up.
 *
 * For STR (Suspend-to-RAM), KEY_POWER press+release is injected, which
 * triggers Android's standard suspend flow via WindowManager / PowerManagerService.
 */
class KeyEventHandler {
public:
    KeyEventHandler(const char* device_path = DEFAULT_KEYEVENT_DEVICE);
    ~KeyEventHandler();

    bool init();
    void destroy();

    /* Inject KEY_POWER press+release to trigger Android suspend flow */
    bool sendPowerKey();

    /* Inject an arbitrary key event */
    bool sendKeyEvent(uint16_t type, uint16_t code, int32_t value);

private:
    bool writeKeyEvent(uint16_t type, uint16_t code, int32_t value);

    std::string mDevicePath;
    int mFd;
    bool mInitialized;
};

#endif
