#include "LogServerImpl.h"
#include <iostream>
#include "LogConfig.h"

using namespace logserver;

LogServerImpl::LogServerImpl() {
}

LogServerImpl::~LogServerImpl() {
    stop();
}

bool LogServerImpl::init() {
    logManager_ = std::make_unique<LogManager>();
    return logManager_->init();
}

bool LogServerImpl::start() {
    logManager_->setFileCreatedCallback(
        std::bind(&LogServerImpl::onLogFileCreated, this, std::placeholders::_1));
    return logManager_->start();
}

bool LogServerImpl::stop() {
    if (logManager_) {
        logManager_->stop();
    }
    return true;
}

void LogServerImpl::getLogSettings(const std::shared_ptr<CommonAPI::ClientId> _client,
                                   getLogSettingsReply_t _reply) {
    std::cout << "[LogServerImpl] getLogSettings called" << std::endl;
    
    LogSettings settings = logManager_->getLogSettings();
    
    LogTypes::LogSettings replySettings;
    replySettings.setRollPeriod(settings.rollPeriod);
    replySettings.setRetainDays(settings.retainDays);
    replySettings.setMaxFileSize(settings.maxFileSize);
    replySettings.setMinLogLevel(static_cast<LogTypes::LogLevel>(settings.minLogLevel));
    replySettings.setEnabledSources(settings.enabledSources);
    replySettings.setLogPath(settings.logPath);
    replySettings.setUsbMountPoint(settings.usbMountPoint);
    replySettings.setUsbExportDir(settings.usbExportDir);
    
    _reply(replySettings);
}

void LogServerImpl::setLogSettings(const std::shared_ptr<CommonAPI::ClientId> _client,
                                   LogTypes::LogSettings _settings,
                                   setLogSettingsReply_t _reply) {
    std::cout << "[LogServerImpl] setLogSettings called" << std::endl;
    
    LogSettings settings;
    settings.rollPeriod = _settings.getRollPeriod();
    settings.retainDays = _settings.getRetainDays();
    settings.maxFileSize = _settings.getMaxFileSize();
    settings.minLogLevel = static_cast<LogLevel>(_settings.getMinLogLevel());
    settings.enabledSources = _settings.getEnabledSources();
    settings.logPath = _settings.getLogPath();
    settings.usbMountPoint = _settings.getUsbMountPoint();
    settings.usbExportDir = _settings.getUsbExportDir();
    
    bool success = logManager_->setLogSettings(settings);
    _reply(success);
}

void LogServerImpl::exportLog(const std::shared_ptr<CommonAPI::ClientId> _client,
                              LogTypes::LogSourceType _sourceType,
                              std::string _startTime,
                              std::string _endTime,
                              std::string _targetPath,
                              exportLogReply_t _reply) {
    std::cout << "[LogServerImpl] exportLog called" << std::endl;
    
    LogSourceType sourceType = static_cast<LogSourceType>(_sourceType);
    std::string exportedFile;
    
    ExportResult result = logManager_->exportLog(sourceType, _startTime, _endTime, 
                                                 _targetPath, exportedFile);
    
    LogTypes::ExportResult replyResult = static_cast<LogTypes::ExportResult>(result);
    _reply(replyResult, exportedFile);
}

void LogServerImpl::onLogFileCreated(const std::string& fileName) {
    std::cout << "[LogServerImpl] Log file created: " << fileName << std::endl;
    
    LogTypes::LogFileInfo fileInfo;
    fileInfo.setFileName(fileName);
    fileInfo.setFileSize(0);
    fileInfo.setCreateTime(0);
    fileInfo.setSourceType(LogTypes::LogSourceType::SYS);
    
    fireNotifyLogFileCreatedEvent(fileInfo);
}