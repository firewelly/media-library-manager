# -*- coding: utf-8 -*-
"""dialogs 子包：对话框。"""

from .import_videos import ImportVideosDialog
from .tag_manager import TagManagerDialog
from .folder_manager import FolderManagerDialog
from .jav_info_dialog import JavInfoDialog
from .actor_detail import ActorDetailWindow
from .actor_browser import ActorBrowserDialog
from .smart_update_dialog import SmartUpdateDialog
from .settings import SettingsDialog
from .duplicates import DuplicatesDialog
from .stats import StatsDialog

__all__ = [
    "ImportVideosDialog",
    "TagManagerDialog",
    "FolderManagerDialog",
    "JavInfoDialog",
    "ActorDetailWindow",
    "ActorBrowserDialog",
    "SmartUpdateDialog",
    "SettingsDialog",
    "DuplicatesDialog",
    "StatsDialog",
]
