"""State names shared by the engine and the tray flow (kept apart so that both can import them without a cycle)."""

# fixture states shown in the UI
NO_USED, OFFLINE, IDLE, WAIT_LOAD, LOADING, TESTING, RESULT, UNLOADING, FAULT = (
    "No Used", "Offline", "Idle", "Wait load", "Loading", "Testing", "Result", "Unloading", "Fault")

STOPPED, RUNNING, PAUSED, RUN_FAULT = "STOPPED", "RUNNING", "PAUSED", "FAULT"
