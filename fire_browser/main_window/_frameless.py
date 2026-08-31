from fire_browser.main_window._deps import *

class _TitleBarDrag(QObject):
    """顶栏拖拽/顶边拉伸：按下瞬间把拖动权交给系统（原生拖动循环），双击最大化/还原。

    说明：不采用"按下后追踪 MouseMove 手动挪窗口"的旧方案——实测本窗口模式下
    按下事件能到、移动事件到不了（2026-08-28 日志实证），系统拖动循环不依赖
    Qt 移动事件，跟手且自带贴边分屏。
    顶边拉伸：最顶端 6px 属于内容区（为了藏系统标题栏），系统不管它，这里
    自行判定——贴顶显示上下拉伸光标，按下交给系统做向上拉伸。
    """
    _EDGE = 6  # 顶边可拉伸判定高度（像素）

    def __init__(self, win, parent=None):
        super().__init__(parent)
        self._win = win

    def _at_top_edge(self, ev):
        """鼠标是否贴在窗口最顶端 _EDGE 像素内"""
        g = ev.globalPosition().toPoint()
        top_y = self._win.mapToGlobal(QPoint(0, 0)).y()
        return 0 <= g.y() - top_y <= self._EDGE

    def eventFilter(self, obj, ev):
        try:
            t = ev.type()
            if t == QEvent.Type.MouseMove:
                # 顶边悬停提示：贴顶显示上下拉伸光标（需要 obj 开启鼠标追踪才有悬停事件）
                if self._at_top_edge(ev):
                    obj.setCursor(Qt.CursorShape.SizeVerCursor)
                else:
                    obj.setCursor(Qt.CursorShape.ArrowCursor)
                return False
            if t == QEvent.Type.MouseButtonPress and ev.button() == Qt.MouseButton.LeftButton:
                _wh = self._win.windowHandle()
                if _wh is None:
                    return False
                if self._at_top_edge(ev):
                    _wh.startSystemResize(Qt.Edge.TopEdge)  # 贴顶：交给系统向上拉伸
                else:
                    if self._win.isMaximized():
                        # 全屏下拖动：先还原成小窗口再交给系统拖（和普通软件一致）
                        self._win.showNormal()
                    _wh.startSystemMove()
                return True
            if t == QEvent.Type.MouseButtonDblClick and ev.button() == Qt.MouseButton.LeftButton:
                if self._win.isMaximized():
                    self._win.showNormal()
                else:
                    self._win.showMaximized()
                return True
        except Exception:
            pass
        return False


class _FramelessNccalcFilter(QAbstractNativeEventFilter):
    """主窗口的系统消息处理：调整"内容区"范围，隐藏系统标题栏、保留原生拉伸边。

    背景：主窗口是"天生普通窗口"（见 FireBrowser.__init__ 注释）。WM_NCCALCSIZE
    里调整"内容区"范围：
    - 普通状态：左/右/下各收一圈"隐形拉伸边"厚度，留在系统手里 → 拉伸光标、拖边
      缩放由系统原生提供（实测 PyQt6 下 WM_NCHITTEST 根本到不了全局过滤器，无法
      自行判定，2026-08-28 日志实证）；顶边不收，标题栏区域整个并入内容区 → 系统
      标题栏不显示；
    - 最大化：四边各收一圈（系统把窗口做得比屏幕大一圈），内容正好铺满屏幕。

    为什么用全局 QAbstractNativeEventFilter：PyQt6 下覆写 QWidget.nativeEvent 必崩
    （见 FireBrowser 踩坑记录），所以由装在事件分发器上的全局过滤器承接。

    ⚠️ 分支体内只允许用 ctypes 调系统接口，绝不能调用 Qt（QCursor/winId 等）：
    消息处理中途重入 Qt 会触发踩坑记录同款访问冲突闪退（2026-08-28 实测）。
    """
    _WM_NCCALCSIZE = 0x0083

    def __init__(self, hwnd_getter):
        super().__init__()
        self._hwnd_getter = hwnd_getter  # 返回主窗口原生句柄（未创建时为 None）

    def nativeEventFilter(self, eventType, message):
        try:
            if eventType != b"windows_generic_MSG":
                return False, 0
            hwnd = self._hwnd_getter()
            if not hwnd:
                return False, 0
            import ctypes as _c
            from ctypes import wintypes as _wt
            class _MSG(_c.Structure):
                _fields_ = [("hwnd", _c.c_void_p), ("message", _c.c_uint),
                            ("wParam", _c.c_size_t), ("lParam", _c.c_size_t)]
            m = _MSG.from_address(int(message))
            if not m.hwnd or m.hwnd != hwnd:
                return False, 0
            if m.message == self._WM_NCCALCSIZE:
                if not m.wParam:
                    return False, 0
                dx = _c.windll.user32.GetSystemMetrics(32) + _c.windll.user32.GetSystemMetrics(92)  # SM_CXSIZEFRAME+SM_CXPADDEDBORDER
                dy = _c.windll.user32.GetSystemMetrics(33) + _c.windll.user32.GetSystemMetrics(92)  # SM_CYSIZEFRAME+SM_CXPADDEDBORDER
                r = _wt.RECT.from_address(m.lParam)
                if _c.windll.user32.IsZoomed(hwnd):
                    # 最大化：系统把窗口做得比屏幕大一圈，四边各收一圈正好铺满屏幕，右下不溢出
                    r.left += dx; r.top += dy; r.right -= dx; r.bottom -= dy
                else:
                    # 普通状态：左/右/下各收一圈隐形拉伸边 → 拉伸光标/拖边缩放由系统原生提供；
                    # 顶边不收（顶到窗口最顶端）→ 标题栏区域整个并入内容区，系统标题栏不显示
                    r.left += dx; r.right -= dx; r.bottom -= dy
                return True, 0
            return False, 0
        except Exception:
            return False, 0
