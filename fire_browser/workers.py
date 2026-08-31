# 快应UI 开源版 - 空壳桩
# 原模块为核心业务逻辑线程序（已删除）。这里只保留导入所需的类名占位，不含任何业务逻辑。
from PyQt6.QtCore import QThread, pyqtSignal


class 任务A(QThread):
    done = pyqtSignal(dict)
    def __init__(self, *a, **k):
        super().__init__()


class 任务B(QThread):
    done = pyqtSignal(dict)
    def __init__(self, *a, **k):
        super().__init__()


class 任务C(QThread):
    def __init__(self, *a, **k):
        super().__init__()


class 任务D(QThread):
    done = pyqtSignal(dict)
    def __init__(self, *a, **k):
        super().__init__()


class 任务E(QThread):
    done = pyqtSignal(dict)
    def __init__(self, *a, **k):
        super().__init__()


class 任务F(QThread):
    done = pyqtSignal(dict)
    def __init__(self, *a, **k):
        super().__init__()