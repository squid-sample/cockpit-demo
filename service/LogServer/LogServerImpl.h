#ifndef LOG_SERVER_IMPL_H
#define LOG_SERVER_IMPL_H

#include <v1/logserver/LogServerStubDefault.hpp>
#include <v1/logserver/LogTypes.hpp>
#include <memory>
#include "LogManager.h"

using namespace v1::logserver;

class LogServerImpl : public LogServerStubDefault
{
public:
    LogServerImpl();
    ~LogServerImpl();

    void getLogSettings(const std::shared_ptr<CommonAPI::ClientId> _client, 
                        getLogSettingsReply_t _reply);
    
    void setLogSettings(const std::shared_ptr<CommonAPI::ClientId> _client, 
                        LogTypes::LogSettings _settings,
                        setLogSettingsReply_t _reply);
    
    void exportLog(const std::shared_ptr<CommonAPI::ClientId> _client,
                   LogTypes::LogSourceType _sourceType,
                   std::string _startTime,
                   std::string _endTime,
                   std::string _targetPath,
                   exportLogReply_t _reply);

    bool init();
    bool start();
    bool stop();

private:
    void onLogFileCreated(const std::string& fileName);
    
    std::unique_ptr<logserver::LogManager> logManager_;
};

#endif