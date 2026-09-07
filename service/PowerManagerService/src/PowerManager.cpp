#define LOG_TAG "PowerManagerService"
#include "log.h"

#include "PowerManager.h"

#define POWER_FDBUS_SERVER_TCP_URL "tcp://0.0.0.0:15001"

PowerManager::PowerManager()
    : mCurrentMode{POWER_MODE_OFF, 0}
    , mRunning(false) {
}

PowerManager::~PowerManager() {
    stop();
}

bool PowerManager::init() {
    /* Initialize fdbus adapter (Link 2) - broadcast to Android native clients */
    mAdapter = std::make_unique<FdbusPowerAdapter>("com.cockpit.power.qnx.service",
                                                     POWER_FDBUS_SERVER_TCP_URL);
    if (!mAdapter->init()) {
        LOG_ERROR("Failed to initialize FdbusPowerAdapter");
        return false;
    }

    /* Initialize keyevent handler (Link 1) - non-fatal if unavailable */
    mKeyHandler = std::make_unique<KeyEventHandler>();
    if (!mKeyHandler->init()) {
        LOG_WARN("KeyEventHandler init failed; STR keyevent link will be inactive");
    }

    /* Initialize STR notifier - non-fatal if unavailable */
    mStrNotifier = std::make_unique<StrNotifier>();
    if (!mStrNotifier->init()) {
        LOG_WARN("StrNotifier init failed; kernel STR notification will be inactive");
    }

    /* Initialize ECD client - fdbus client connecting to ECDService */
    mEcdClient = std::make_unique<EcdClient>();
    if (!mEcdClient->init()) {
        LOG_ERROR("Failed to initialize EcdClient");
        return false;
    }

    /* Wire the power mode callback */
    mEcdClient->setPowerModeHandler(
        std::bind(&PowerManager::handlePowerMode, this, std::placeholders::_1));

    /* Set initial mode on the fdbus adapter for late subscribers */
    mAdapter->setCurrentPowerMode(mCurrentMode);

    mRunning = true;
    LOG_INFO("PowerManager initialized");
    return true;
}

void PowerManager::run() {
    std::unique_lock<std::mutex> lock(mRunMutex);
    mRunCond.wait(lock, [this]{ return !mRunning; });
}

void PowerManager::stop() {
    {
        std::lock_guard<std::mutex> lock(mRunMutex);
        mRunning = false;
    }
    mRunCond.notify_one();

    if (mEcdClient) {
        mEcdClient->destroy();
        mEcdClient.reset();
    }
    if (mKeyHandler) {
        mKeyHandler->destroy();
        mKeyHandler.reset();
    }
    if (mStrNotifier) {
        mStrNotifier->destroy();
        mStrNotifier.reset();
    }
    if (mAdapter) {
        mAdapter->destroy();
    }
}

bool PowerManager::handlePowerMode(const PowerModeInfo& power_info) {
    LOG_INFO("handlePowerMode: mode=%d", (int)power_info.mode);

    {
        std::lock_guard<std::mutex> lock(mStateMutex);
        mCurrentMode = power_info;
    }

    if (power_info.mode == POWER_MODE_STR) {
        return forwardStr(power_info);
    } else {
        return forwardNormal(power_info);
    }
}

bool PowerManager::forwardStr(const PowerModeInfo& power_info) {
    (void)power_info;
    LOG_INFO("forwardStr: processing STR mode (Link 1 keyevent + kernel STR notification, NO fdbus per spec)");

    bool key_ok = false;
    bool str_ok = false;

    if (mKeyHandler) {
        key_ok = mKeyHandler->sendPowerKey();
        if (!key_ok) {
            LOG_ERROR("forwardStr: Link 1 keyevent sendPowerKey() failed");
        }
    } else {
        LOG_ERROR("forwardStr: KeyEventHandler unavailable, Link 1 keyevent skipped");
    }

    if (mStrNotifier) {
        str_ok = mStrNotifier->notifyStr();
        if (!str_ok) {
            LOG_ERROR("forwardStr: StrNotifier notifyStr() failed");
        }
    } else {
        LOG_ERROR("forwardStr: StrNotifier unavailable, kernel STR notification skipped");
    }

    return key_ok && str_ok;
}

bool PowerManager::forwardNormal(const PowerModeInfo& power_info) {
    LOG_INFO("forwardNormal: mode=%d (Link 2 fdbus broadcast)", (int)power_info.mode);

    if (mAdapter) {
        bool ok = mAdapter->broadcastPowerMode(power_info);
        if (!ok) {
            LOG_ERROR("forwardNormal: fdbus broadcastPowerMode failed, mode=%d",
                      (int)power_info.mode);
        }
        return ok;
    } else {
        LOG_ERROR("forwardNormal: fdbus adapter unavailable, cannot forward mode=%d",
                  (int)power_info.mode);
        return false;
    }
}

PowerModeInfo PowerManager::getCurrentMode() const {
    std::lock_guard<std::mutex> lock(mStateMutex);
    return mCurrentMode;
}
