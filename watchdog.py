# 快应UI 开源版 - 空壳桩
# 原模块是看护/自启逻辑（核心，已删）。只保留启动所需的最小接口。


def _noop(*_a, **_k):
    return None


def run_watchdog(*_a, **_k):
    return _noop


def spawn_watchdog(*_a, **_k):
    return _noop