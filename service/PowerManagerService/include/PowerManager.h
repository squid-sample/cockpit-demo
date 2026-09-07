#ifndef __POWER_MANAGER_H__
#define __POWER_MANAGER_H__

#include "PowerManagerCommon.h"
#include "Singleton.h"
#include "EcdClient.h"
#include "FdbusPowerAdapter.h"
#include "KeyEventHandler.h"
#include "StrNotifier.h"
#include <memory>
#include <mutex>
#include <condition_variable>

/*
 * PowerManager: singleton orchestrator.
 *
 *   ┌──────┐   SPI   ┌────────────┐  fdbus   ┌──────────┐
 *   │ MCU  │ ───────▶│ ECDService │ ────────▶│ EcdClient │
 *   └──────┘         └────────────┘          └─────┬────┘
 *                                                   │ PowerModeHandler
 *                                                   │
 *                                        ┌──────────▼──────────┐
 *                                        │   PowerManager      │
 *                                        └──┬────────┬─────┬───┘
 *                   STR ─────────────────────┐  │     │     │
 *                                           │  │     │     │
 *                                     ┌─────▼──▼┐ ┌──▼───┐ ┌▼────────┐
 *                                     │ KeyEvt  │ │ STR  │ │ Fdbus   │
 *                                     │ Handler │ │Notify│ │ Adapter │
 *                                     │(Link 1) │ │kernel│ │(Link 2) │
 *                                     └─────────┘ └──────┘ │broadcast│
 *                                     KEY_POWER→Android    │→clients │
 *                                                           └─────────┘
 *                  Other modes ──────────────────────────────┘
 */
class PowerManager {
public:
    bool init();
    void run();
    void stop();

    bool handlePowerMode(const PowerModeInfo& power_info);
    PowerModeInfo getCurrentMode() const;

private:
    PowerManager();
    ~PowerManager();

    bool forwardStr(const PowerModeInfo& power_info);
    bool forwardNormal(const PowerModeInfo& power_info);

    std::unique_ptr<EcdClient> mEcdClient;
    std::unique_ptr<FdbusPowerAdapter> mAdapter;
    std::unique_ptr<KeyEventHandler> mKeyHandler;
    std::unique_ptr<StrNotifier> mStrNotifier;

    mutable std::mutex mStateMutex;
    PowerModeInfo mCurrentMode;

    std::mutex mRunMutex;
    std::condition_variable mRunCond;
    bool mRunning;

    DECLARE_SINGLETON_FRIEND(PowerManager)
};

#endif
