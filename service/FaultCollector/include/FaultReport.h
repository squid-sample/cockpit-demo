#ifndef __FAULT_REPORT_H__
#define __FAULT_REPORT_H__

#include "FaultCommon.h"
#include <string>

class FaultReport {
public:
    FaultReport();
    ~FaultReport();

    bool init();
    void destroy();

    int report(fault_code_t fault_code, const std::string& msg = "", bool is_recover = false);
    int reportAsync(fault_code_t fault_code, const std::string& msg = "", bool is_recover = false);

    bool isConnected() const;

private:
    bool connectToService();
    void disconnect();

    int mCoId;
    bool mConnected;
};

#endif