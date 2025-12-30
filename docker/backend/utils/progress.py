from dataclasses import dataclass
from typing import Callable, Optional

@dataclass
class ProgressState:
    scanned: int = 0
    added: int = 0
    updated: int = 0
    skipped: int = 0
    percent: float = 0.0
    message: str = ""

class ProgressUpdateManager:
    def __init__(self, cb: Optional[Callable[[ProgressState], None]] = None):
        self.cb = cb
        self.state = ProgressState()

    def update(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self.state, k, v)
        if self.cb:
            self.cb(self.state)

