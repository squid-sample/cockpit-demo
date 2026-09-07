#ifndef __POWER_MANAGER_COMMON_H__
#define __POWER_MANAGER_COMMON_H__

#pragma once

#include <stdint.h>

#pragma pack(1)

/*
 * Power mode received from MCU.
 * Values are kept consistent with the PowerState enumeration defined in
 * service/api/fidl/HelloWorld.fidl so that the Android side can reuse
 * the same numbering scheme.
 */
typedef enum {
    POWER_MODE_OFF       = 0,
    POWER_MODE_STR       = 1,   /* Suspend-to-RAM */
    POWER_MODE_ACTIVE    = 2,
    POWER_MODE_SHUTDOWN  = 3,
    POWER_MODE_RESTART   = 4,
    POWER_MODE_DEEP_SLEEP = 5
} PowerMode;

typedef struct {
    PowerMode mode;
    uint64_t timestamp;
} PowerModeInfo;

#define POWER_SERVICE_NAME "PowerManagerService"

typedef struct {
    uint32_t type;
    PowerModeInfo power_info;
} PowerMessage;

#define MSG_TYPE_SET_POWER_MODE 0x01
#define MSG_TYPE_GET_POWER_MODE 0x02

typedef struct {
    int32_t status;
    PowerModeInfo current_mode;
} PowerReply;

/* fdbus message codes */
#define FDB_MSG_ECD_POWER_STATE     0x2001  /* ECDService broadcasts power state */
#define FDB_MSG_POWER_MODE_BROADCAST 0x1001  /* PowerManager broadcasts to Android clients */

/* KeyEvent constants (Linux input_event compatible) */
#define EV_SYN          0x00
#define SYN_REPORT      0
#define EV_KEY          0x01
#define KEY_POWER       116

/* Default paths (platform-specific, configurable at runtime) */
#define DEFAULT_KEYEVENT_DEVICE  "/dev/input/event0"
#define DEFAULT_PM_DEVICE_PATH   "/dev/pm"
#define DEFAULT_PM_STR_CMD       0x0001   /* devctl command code for STR */
#define DEFAULT_ECD_SERVICE_URL  "tcp://127.0.0.1:15000"

#pragma pack()

#endif
