"""Tên trạng thái dùng chung cho engine và luồng tray (để riêng để cả hai import được mà không bị import vòng)."""

# trạng thái fixture hiển thị trên UI
NO_USED, OFFLINE, IDLE, LOADING, TESTING, RESULT, UNLOADING, FAULT = (
    "No Used", "Offline", "Idle", "Loading", "Testing", "Result", "Unloading", "Fault")

STOPPED, RUNNING, PAUSED, RUN_FAULT = "STOPPED", "RUNNING", "PAUSED", "FAULT"
