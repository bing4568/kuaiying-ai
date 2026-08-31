# 快应AI - 纯UI小件模块：滚动条样式/消息卡片/加载动画/加载遮罩/JS回调安全包装
# 只依赖 PyQt6，不依赖业务逻辑，可供店铺标签页/设置中心等共用。
from PyQt6.QtCore import Qt, QPoint, QRectF, QTimer, QEvent
from PyQt6.QtGui import QColor, QPainter, QPen, QTextOption
from PyQt6.QtWidgets import (
    QWidget, QSizePolicy, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QFrame,
)

SCROLLBAR_STYLE = """
    QScrollBar:horizontal {
        border: 0; background: #f0f1f5; height: 8px; margin: 0;
    }
    QScrollBar:vertical {
        border: 0; background: #f0f1f5; width: 8px; margin: 0;
    }
    QScrollBar::handle {
        background: #c0c6d4; border-radius: 4px; min-width: 24px; min-height: 24px;
    }
    QScrollBar::handle:hover {
        background: #165dff;
    }
    QScrollBar::handle:pressed {
        background: #0e42d2;
    }
    QScrollBar::add-line, QScrollBar::sub-line {
        border: 0; background: transparent; width: 0px; height: 0px;
    }
    QScrollBar::add-page, QScrollBar::sub-page {
        background: transparent;
    }
"""


class MsgCard(QWidget):
    """卡片控件 - 标题+内容，内容自动换行，卡片高度随内容伸缩（超10行内部滚动）"""
    def __init__(self, record, on_click=None, parent=None):
        super().__init__(parent)
        self._record = record  # 记录数据（标题、内容、时间等）
        self._on_click = on_click  # 点击卡片时触发的回调函数
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)  # 卡片水平撑满列表
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)  # 让样式表背景/圆角生效
        self.setStyleSheet("""
            MsgCard { background: #ffffff; border-radius: 10px; }
            MsgCard:hover { background: #f3f4f6; }
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 6, 14, 6)
        outer.setSpacing(2)

        is_notice = record.get('msg_type') == '公告'
        # 顶部行：标题或类型标签 + 未读红点 + 时间
        head = QHBoxLayout()
        head.setSpacing(6)
        if is_notice:
            tag = QLabel(record.get('buyer_nickname', '公告'))  # 公告：第一行直接显示标题
        else:
            tag = QLabel(record.get('msg_type', '消息'))  # 其它消息：显示类型
        tag.setStyleSheet("background: transparent; border: none; font-size: 12px; font-weight: bold; color: #000000;")
        head.addWidget(tag)
        head.addStretch()
        dot = None
        if not record.get('viewed', False):
            dot = QLabel("●")
            dot.setStyleSheet("background: transparent; border: none; font-size: 10px; color: #ef4444;")
            head.addWidget(dot)
        t_label = QLabel(record.get('time', ''))
        t_label.setStyleSheet("background: transparent; border: none; font-size: 11px; color: #9ca3af;")
        head.addWidget(t_label)
        outer.addLayout(head)

        nick = record.get('buyer_nickname', record['buyer_uid'])
        nick_label = None
        if not is_notice:
            # 标题行（仅非公告类型显示昵称，公告标题已在第一行）
            nick_label = QLabel(nick)
            nick_label.setStyleSheet("background: transparent; border: none; font-size: 12px; font-weight: bold; color: #1f2937;")
            nick_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)  # 标题行撑满整行，靠左显示
            outer.addWidget(nick_label)

        # 内容区：只读文本框，自动换行，超高内部滚动
        self._content = QTextEdit()
        self._content.setReadOnly(True)
        self._content.setFrameShape(QFrame.Shape.NoFrame)
        self._content.setStyleSheet("background: transparent; border: none; padding: 0px; font-size: 12px; color: #6b7280;")
        self._content.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._content.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._content.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self._content.setPlainText(record.get('msg_text', ''))
        self._content.document().setDocumentMargin(0)  # 去掉内容四周留白，更紧凑
        self._content.setViewportMargins(0, 0, 0, 0)  # 去掉文本框内部自带边距，避免左侧留空
        self._content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._content.verticalScrollBar().setStyleSheet(SCROLLBAR_STYLE)
        outer.addWidget(self._content)

        # 点击转发：标签、标题、内容区都响应卡片点击（滚动条除外）
        _click_targets = [tag, t_label, self._content.viewport()]
        if dot is not None:
            _click_targets.append(dot)
        if nick_label is not None:
            _click_targets.append(nick_label)
        for _w in _click_targets:
            _w.installEventFilter(self)
        self._content.installEventFilter(self)

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Type.MouseButtonPress:
            if self._on_click:
                self._on_click(self._record)
            return True
        return super().eventFilter(obj, ev)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._fit_content()

    def showEvent(self, e):
        super().showEvent(e)
        self._fit_content()

    def _fit_content(self):
        """内容区高度自适应：内容多高就多高，最多6行，超出内部滚动"""
        width = self._content.viewport().width()
        if width <= 0:
            return
        self._content.document().setTextWidth(width)
        doc_h = int(self._content.document().size().height())
        max_h = 6 * 20 + 4  # 最多显示6行，超出滚动
        self._content.setFixedHeight(min(max(doc_h, 24), max_h))

    def mousePressEvent(self, e):
        if self._on_click:
            self._on_click(self._record)
        e.accept()


class _LoadingSpinner(QWidget):
    """加载动画（旋转圆弧）：纯 Qt 自绘，无第三方依赖。
    只在可见时转动（showEvent 启动 / hideEvent 停止），浮层消失后零 CPU 占用。"""

    def __init__(self, parent=None, size=44):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._angle = 0
        self._color = QColor('#165dff')  # 与全局主色一致（选中蓝）
        self._timer = QTimer(self)
        self._timer.setInterval(16)  # 60帧/秒：转圈更顺滑
        self._timer.timeout.connect(self._tick)

    def _tick(self):
        self._angle = (self._angle + 6) % 360
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self._color, 3.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        m = pen.widthF() / 2 + 1
        r = QRectF(m, m, self.width() - 2 * m, self.height() - 2 * m)
        # 一段120°圆弧绕圈转：主流"转圈"动效的极简画法
        p.drawArc(r, -self._angle * 16, -120 * 16)
        p.end()

    def showEvent(self, ev):
        self._timer.start()
        super().showEvent(ev)

    def hideEvent(self, ev):
        self._timer.stop()
        super().hideEvent(ev)


class LoadingMask(QWidget):
    """加载中提示浮窗：独立小窗口飘在网页区上方（Edge 空域盖不住），页面就绪后自动消失。
    供店铺标签页/设置中心等内嵌网页的弹窗共用。"""

    def __init__(self, anchor, text="正在加载页面，请稍候…", timeout_ms=15000):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self._anchor = anchor  # 被盖住的网页控件（QWidget）
        self.setStyleSheet("background:#f5f6f8; border:none;")
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 转圈动画 + 提示文字（动画只在浮层显示期间转动）
        self._spinner = _LoadingSpinner(self)
        lay.addWidget(self._spinner, 0, Qt.AlignmentFlag.AlignCenter)
        lay.addSpacing(12)
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color:#6b7280; font-size:14px; background:transparent; border:none;")
        lay.addWidget(lbl)
        # 跟随锚点控件移动/缩放/销毁
        anchor.installEventFilter(self)
        # 兜底：超时自动消失（断网等加载永远不完成的情况）
        QTimer.singleShot(timeout_ms, self.dismiss)

    def eventFilter(self, obj, ev):
        if obj is self._anchor:
            if ev.type() in (QEvent.Type.Move, QEvent.Type.Resize, QEvent.Type.Show):
                self.sync_pos()
            elif ev.type() == QEvent.Type.Hide:
                self.hide()
            elif ev.type() in (QEvent.Type.Destroy, QEvent.Type.Close):
                self.dismiss()
        return super().eventFilter(obj, ev)

    def sync_pos(self):
        try:
            if self._anchor is None or not self._anchor.isVisible():
                return
            g = self._anchor.mapToGlobal(QPoint(0, 0))
            self.setGeometry(g.x(), g.y(), self._anchor.width(), self._anchor.height())
            if not self.isVisible():
                self.show()
        except Exception:
            pass

    def dismiss(self):
        try:
            self._anchor = None
            self.hide()
            self.deleteLater()
        except Exception:
            pass


def _attach_loading_mask(web_view, text="正在加载页面，请稍候…", delay_ms=200):
    """给内嵌网页控件挂"加载中"浮窗：加载完成（再缓 delay_ms 让画面上屏）后自动消失。
    返回浮窗对象（调用方可保存引用，关闭页面时主动 dismiss）。"""
    try:
        mask = LoadingMask(web_view, text)
        web_view._loading_mask = mask
        web_view.loadFinished.connect(lambda ok: QTimer.singleShot(delay_ms, mask.dismiss))
        # 关闭网页控件时一并收走浮窗
        _orig_delete = web_view.deleteLater
        def _delete_with_mask():
            try:
                mask.dismiss()
            except Exception:
                pass
            _orig_delete()
        web_view.deleteLater = _delete_with_mask
        QTimer.singleShot(150, mask.sync_pos)
        return mask
    except Exception:
        return None


def _js_cb_safe(fn):
    """网页JS回调异常防护装饰器：回调里任何异常只记日志，绝不穿透回网页内核。
    （异常穿透会在内核回调/析构边界引发原生访问冲突——卡死元凶，2026-08-28）"""
    def _wrapped(self, *a, **k):
        try:
            return fn(self, *a, **k)
        except Exception:
            try:
                import traceback as _tb
                self._log_diag("[JS回调异常] " + _tb.format_exc()[:600])
            except Exception:
                pass
    return _wrapped