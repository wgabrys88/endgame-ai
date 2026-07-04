from __future__ import annotations
import ctypes
import shutil
import time
from typing import Any

class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [('ACLineStatus', ctypes.c_byte), ('BatteryFlag', ctypes.c_byte), ('BatteryLifePercent', ctypes.c_byte), ('SystemStatusFlag', ctypes.c_byte), ('BatteryLifeTime', ctypes.c_ulong), ('BatteryFullLifeTime', ctypes.c_ulong)]

_kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

def power_status() -> dict[str, Any]:
    st = SYSTEM_POWER_STATUS()
    if not _kernel32.GetSystemPowerStatus(ctypes.byref(st)):
        return {'available': False}
    pct = int(st.BatteryLifePercent)
    if pct > 100:
        pct = None
    return {'available': True, 'on_ac': st.ACLineStatus == 1, 'battery_percent': pct, 'battery_flag': int(st.BatteryFlag), 'low_battery': pct is not None and pct < 20 and st.ACLineStatus != 1}

def disk_free(root: str='C:\\') -> dict[str, Any]:
    usage = shutil.disk_usage(root)
    return {'root': root, 'free_gb': round(usage.free / 1024 ** 3, 2), 'total_gb': round(usage.total / 1024 ** 3, 2)}

def collect(state: dict[str, Any]) -> dict[str, Any]:
    power = power_status()
    urgency = 'normal'
    if power.get('low_battery'):
        urgency = 'high'
    elif power.get('available') and not power.get('on_ac') and power.get('battery_percent') is not None and power['battery_percent'] < 35:
        urgency = 'elevated'
    return {'power': power, 'disk': disk_free(), 'focused_title': state.get('focused_title', ''), 'failure_streak': int((state.get('failure_streak') or {}).get('count', 0) or 0), 'tick': int(state.get('tick', 0) or 0), 'has_observation': bool(state.get('desktop_tree_text')), 'urgency': urgency, 'collected_at': time.time()}