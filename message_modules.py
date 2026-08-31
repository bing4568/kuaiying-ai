# 快应UI 开源版 - 空壳桩
# 原模块为核心业务逻辑（已删除）。只保留启动所需的最小接口。


class ReplyEngine:
    def __init__(self, *a, **k):
        pass

    def __getattr__(self, name):
        return _noop


class MessageSender:
    def __init__(self, *a, **k):
        pass

    def __getattr__(self, name):
        return _noop


def _noop(*_a, **_k):
    return None