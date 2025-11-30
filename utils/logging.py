import sys
from datetime import datetime

class LogLevel:
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

_CURRENT_LEVEL = LogLevel.INFO
_LEVEL_ORDER = {
    LogLevel.DEBUG: 10,
    LogLevel.INFO: 20,
    LogLevel.WARNING: 30,
    LogLevel.ERROR: 40,
    LogLevel.CRITICAL: 50,
}

def set_log_level(level: str):
    global _CURRENT_LEVEL
    _CURRENT_LEVEL = level

def output_log(level: str, message: str, sink=None):
    if _LEVEL_ORDER[level] < _LEVEL_ORDER[_CURRENT_LEVEL]:
        return
    ts = datetime.now().strftime('%H:%M:%S')
    formatted = f"{ts} - [{level}] {message}"
    print(formatted)
    if sink:
        try:
            sink(formatted)
        except Exception:
            pass

