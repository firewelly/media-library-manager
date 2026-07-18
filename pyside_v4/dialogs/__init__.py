# -*- coding: utf-8 -*-
"""
pyside_v4.dialogs - 对话框窗口
"""

from .actor_dialog import ActorDialog
from .tag_dialog import TagDialog
from .scan_dialog import ScanDialog
from .settings_dialog import SettingsDialog
from .task_progress_dialog import TaskProgressDialog
from .folder_dialog import FolderDialog
from .smart_update_dialog import SmartUpdateDialog
from .dedup_dialog import DedupDialog

__all__ = [
    'ActorDialog', 'TagDialog', 'ScanDialog', 'SettingsDialog',
    'TaskProgressDialog', 'FolderDialog', 'SmartUpdateDialog', 'DedupDialog'
]
