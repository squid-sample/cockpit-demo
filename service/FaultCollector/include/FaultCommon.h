#ifndef __FAULT_COMMON_H__
#define __FAULT_COMMON_H__

#pragma once

#pragma pack(1)

typedef uint32_t fault_code_t;

typedef struct {
    uint32_t fault_code : 8;
    uint32_t module_code : 8;
    uint32_t domain : 8;
    uint32_t os_type : 4;
    uint32_t severity : 4;
} FaultCodeBits;

typedef union {
    fault_code_t code;
    FaultCodeBits bits;
} FaultCode;

typedef enum {
    FAULT_STATUS_PENDING = 0x01,
    FAULT_STATUS_REPORTED = 0x02,
    FAULT_STATUS_CONFIRMED = 0x04
} FaultStatus;

typedef struct {
    fault_code_t fault_code;
    uint64_t timestamp;
    uint8_t status;
} FaultInfo;

#define FAULT_SERVICE_NAME "FaultCollector"

#define MAX_MSG_SIZE 256

typedef struct {
    uint32_t type;
    FaultInfo fault_info;
    char message[128];
} FaultMessage;

#define MSG_TYPE_REPORT_SYNC 0x01
#define MSG_TYPE_REPORT_ASYNC 0x02
#define MSG_TYPE_ACK 0x03

#define PULSE_CODE_HAM_PROCESS_EXIT 0x01
#define PULSE_CODE_HAM_PROCESS_CRASH 0x02
#define PULSE_CODE_HAM_WATCHDOG_TIMEOUT 0x03
#define PULSE_CODE_HAM_RESOURCE_EXHAUSTED 0x04

typedef struct {
    int32_t status;
} FaultReply;

#define FAULT_CODE_HAM_BASE 0xF0
#define FAULT_CODE_HAM_PROCESS_CRASH BUILD_FAULT_CODE(FAULT_CODE_HAM_BASE + 1, 0, FAULT_DOMAIN_SECURITY, FAULT_OS_QNX, FAULT_SEVERITY_FATAL)
#define FAULT_CODE_HAM_WATCHDOG_TIMEOUT BUILD_FAULT_CODE(FAULT_CODE_HAM_BASE + 2, 0, FAULT_DOMAIN_SECURITY, FAULT_OS_QNX, FAULT_SEVERITY_FATAL)
#define FAULT_CODE_HAM_RESOURCE_EXHAUSTED BUILD_FAULT_CODE(FAULT_CODE_HAM_BASE + 3, 0, FAULT_DOMAIN_PERFORMANCE, FAULT_OS_QNX, FAULT_SEVERITY_ERROR)
#define FAULT_CODE_FC_CRASH_RECOVERY BUILD_FAULT_CODE(FAULT_CODE_HAM_BASE + 4, 0, FAULT_DOMAIN_SECURITY, FAULT_OS_QNX, FAULT_SEVERITY_WARNING)

typedef enum {
    FAULT_SEVERITY_INFO = 0x1,
    FAULT_SEVERITY_WARNING = 0x2,
    FAULT_SEVERITY_ERROR = 0x4,
    FAULT_SEVERITY_FATAL = 0x8
} FaultSeverity;

typedef enum {
    FAULT_OS_QNX = 0x1,
    FAULT_OS_ANDROID = 0x2,
    FAULT_OS_MCU = 0x4
} FaultOsType;

typedef enum {
    FAULT_DOMAIN_COMM = 0x01,
    FAULT_DOMAIN_SECURITY = 0x02,
    FAULT_DOMAIN_BUSINESS = 0x03,
    FAULT_DOMAIN_PERFORMANCE = 0x04
} FaultDomain;

#define BUILD_FAULT_CODE(fault, module, domain, os, severity) \
    ((fault_code_t)(fault) | \
     ((fault_code_t)(module) << 8) | \
     ((fault_code_t)(domain) << 16) | \
     ((fault_code_t)(os) << 24) | \
     ((fault_code_t)(severity) << 28))

#pragma pack()

#endif