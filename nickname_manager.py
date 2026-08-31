# 快应UI 开源版 - 空壳桩
# 原模块为核心业务逻辑（已删除）。只保留启动所需的最小接口。
class NicknameManager:
    def __init__(self, *a, **k):
        pass

    def clean_expired(self, *a, **k):
        return

    def get(self, *a, **k):
        return ''

    def update(self, *a, **k):
        return

    def __getattr__(self, name):
        def _noop(*_a, **_k):
            return None
        return _noop