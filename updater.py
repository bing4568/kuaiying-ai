# 快应UI 开源版 - 空壳桩
# 原模块是自动更新逻辑（核心，已删）。只保留启动所需的最小接口。
class _Sig:
    def connect(self, *a, **k):
        return self
    def emit(self, *a, **k):
        pass


class Updater:
    def __init__(self, *a, **k):
        self.status_changed = _Sig()
        self.apply_ready = _Sig()
        self._start_apply = _Sig()

    def check_update(self, *a, **k):
        pass

    def apply_update(self, *a, **k):
        pass