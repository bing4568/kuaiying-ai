# 快应UI 开源版 - 空壳桩
# 原模块为核心业务逻辑（已删除）。只保留启动所需的最小接口。
from PyQt6.QtCore import QObject, pyqtSignal


def _noop(*_a, **_k):
    return None


def warm_settings_network(*_a, **_k):
    return None


class ReplySettingsBridge(QObject):
    _page_file_ready = pyqtSignal(bool)
    _reload_requested = pyqtSignal()
    _rsc_save_error = pyqtSignal(str)
    _profile_refreshed = pyqtSignal(str)
    _missed_ready = pyqtSignal(str)

    def __init__(self, *a, **k):
        super().__init__()
        self._rsc_models_cache = None
        self._rsc_last_html = ''

    def __getattr__(self, name):
        return _noop