# 快应AI - fire_browser.main_window 的依赖聚合模块
# 复用 browser_tab 的依赖全集，再补主窗口特有的名字；各零件文件统一 `from ._deps import *`。

from fire_browser.browser_tab._deps import *

from PyQt6.QtWidgets import (
    QMainWindow, QStackedWidget, QSystemTrayIcon, QToolBar, QStatusBar,
)
from fire_browser.browser_tab import BrowserTab

# ── 测试模式模块清单（测试.bat 拉起时用）：每个模块可单独开关，定位卡死元凶 ──
# 开源演示版：仅保留占位标签，不再对应任何业务模块
_TEST_MODULES = ['模块A', '模块B', '模块C', '模块D', '模块E', '模块F', '模块G', '模块H']

# ── 数据库可用性（原 main_qt 模块初始化时判断，供生命周期等零件取用）──
try:
    import database
    HAS_DB = True
except Exception:
    HAS_DB = False

__all__ = [n for n in globals() if not n.startswith('__')]