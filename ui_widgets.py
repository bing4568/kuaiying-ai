# 快应AI - 自绘UI组件
import os
import time
from PyQt6.QtWidgets import (QPushButton, QWidget, QSizePolicy, QCheckBox, QDialog,
                             QVBoxLayout, QHBoxLayout, QLabel, QTabBar,
                             QGraphicsDropShadowEffect)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QTimer, QPoint
from PyQt6.QtGui import (QPainter, QPen, QBrush, QColor, QFont, QFontMetrics,
                         QPolygonF, QPainterPath, QTextLayout, QPixmap)
from PyQt6.QtCore import QPointF, QRectF, QRect

FONT_FAMILY = "Microsoft YaHei"


def _make_msg_dialog(parent, title, text, ok_text, cancel_text=None, accent="#165dff"):
    """自绘提示弹窗骨架：标题栏无问号，文字与按钮全部用微软雅黑（按钮为自绘）。
    返回 (对话框, 确认按钮, 取消按钮)；取消按钮为 None 时只放一个按钮"""
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setWindowFlags(dlg.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)  # 去掉标题栏问号
    dlg.setFixedWidth(420)
    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(24, 20, 24, 16)
    lay.setSpacing(16)
    lbl = QLabel(text)
    lbl.setFont(QFont(FONT_FAMILY, 10))
    lbl.setWordWrap(True)
    lbl.setStyleSheet("color: #1f2937; background: transparent;")
    lay.addWidget(lbl)
    bar = QHBoxLayout()
    bar.addStretch()
    btn_ok = CustomButton(ok_text, bg=accent, fg="#ffffff", parent=dlg, font_size=13)
    btn_ok.setMinimumWidth(88)
    bar.addWidget(btn_ok)
    btn_cancel = None
    if cancel_text:
        btn_cancel = CustomButton(cancel_text, bg="#e5e7eb", fg="#374151", parent=dlg, font_size=13)
        btn_cancel.setMinimumWidth(88)
        bar.addWidget(btn_cancel)
    lay.addLayout(bar)
    return dlg, btn_ok, btn_cancel


def ask_confirm(parent, title, text):
    """确认弹窗（自绘）：按钮为「确认/取消」，微软雅黑字体，标题栏无问号。
    点确认返回 True，点取消返回 False"""
    dlg, btn_ok, btn_cancel = _make_msg_dialog(parent, title, text, "确认", "取消")
    btn_ok.clicked.connect(dlg.accept)
    btn_cancel.clicked.connect(dlg.reject)
    return dlg.exec() == QDialog.DialogCode.Accepted


def msg_info(parent, title, text):
    """信息提示弹窗（自绘）：微软雅黑、「确定」、无问号"""
    dlg, btn_ok, _ = _make_msg_dialog(parent, title, text, "确定")
    btn_ok.clicked.connect(dlg.accept)
    dlg.exec()


def msg_warn(parent, title, text):
    """警告提示弹窗（自绘）：微软雅黑、「确定」、无问号"""
    dlg, btn_ok, _ = _make_msg_dialog(parent, title, text, "确定", accent="#f59e0b")
    btn_ok.clicked.connect(dlg.accept)
    dlg.exec()


def msg_critical(parent, title, text):
    """错误提示弹窗（自绘）：微软雅黑、「确定」、无问号"""
    dlg, btn_ok, _ = _make_msg_dialog(parent, title, text, "确定", accent="#ef4444")
    btn_ok.clicked.connect(dlg.accept)
    dlg.exec()


class CustomButton(QPushButton):
    """自绘按钮：QPainter 绘制，字体保证为 Microsoft YaHei"""
    def __init__(self, text="", bg="#165dff", fg="#ffffff", parent=None,
                 font_size=13, radius=6, height=36, bold=True, disabled=False, icon_size=0, no_bg=False,
                 align_center=True):
        super().__init__(parent)
        self._align_center = align_center  # 图标+文字是否整体居中（False=左对齐）
        self._text = text          # 按钮文字
        self._bg = QColor(bg)      # 背景色（默认蓝色）
        self._fg = QColor(fg)      # 文字颜色（默认白色）
        self._font_size = font_size  # 字号
        self._radius = radius      # 圆角半径
        self._bold = bold          # 是否加粗
        self._icon_size = icon_size  # 图标尺寸（0=无图标）
        self._no_bg = no_bg        # 是否无背景（纯文字按钮）
        self._hover_bg = self._bg.lighter(115)  # 悬停时的背景色（变亮15%）
        self._hover_fg = self._fg.lighter(130)  # 悬停时的文字色
        self._current_bg = self._bg  # 当前实际背景色（根据悬停状态变化）
        self._hover = False        # 鼠标是否悬停在按钮上
        self._enabled = not disabled  # 按钮是否可用
        self._orig_bg = QColor(bg)  # 原始背景色（恢复用）
        self._orig_fg = QColor(fg)  # 原始文字色（恢复用）
        self.setEnabled(self._enabled)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(height)
        self.setCursor(Qt.CursorShape.PointingHandCursor if self._enabled else Qt.CursorShape.ArrowCursor)
        self.setStyleSheet("")

    def sizeHint(self):
        fm = self.fontMetrics()
        w = fm.horizontalAdvance(self._text) + 48
        if self._icon_size:
            w += self._icon_size - self._font_size
        return QSize(max(w, 80), self.minimumHeight())

    def setText(self, text):
        super().setText(text)
        self._text = text
        self.update()

    def setEnabled(self, enabled):
        super().setEnabled(enabled)
        self._enabled = enabled
        self.setCursor(Qt.CursorShape.PointingHandCursor if enabled else Qt.CursorShape.ArrowCursor)
        self.update()

    def enterEvent(self, e):
        if self._enabled:
            self._hover = True; self._current_bg = self._hover_bg; self.update()

    def leaveEvent(self, e):
        if self._enabled:
            self._hover = False; self._current_bg = self._bg; self.update()

    def mousePressEvent(self, e):
        if self._enabled:
            self._current_bg = self._bg.darker(115); self.update()
            super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        if self._enabled:
            self._current_bg = self._hover_bg if self._hover else self._bg; self.update()
            super().mouseReleaseEvent(e)

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1); self._draw(p, r); p.end()

    def _draw(self, p, r):
        bg = self._current_bg
        fg = self._fg
        if self._no_bg and self._hover and self._enabled:
            fg = self._hover_fg
        if not self._enabled:
            bg = QColor("#d1d5db"); fg = QColor("#9ca3af")
        if not self._no_bg:
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(bg))
            p.drawRoundedRect(r, self._radius, self._radius)
        if self._icon_size and ' ' in self._text:
            icon_char = self._text.split(' ', 1)[0]
            label_part = self._text.split(' ', 1)[1]
            p.setPen(QPen(fg))
            fl = QFont(FONT_FAMILY, self._font_size); fl.setBold(self._bold)
            fl_m = QFontMetrics(fl)
            icon_w = int(self._icon_size * 0.7)
            label_w = fl_m.width(label_part)
            gap = 4
            total_w = icon_w + gap + label_w
            if self._align_center:
                start_x = r.left() + (r.width() - total_w) // 2
            else:
                start_x = r.left() + 8  # 左对齐（靠左边留一点边距）
            cy = r.center().y()
            sz = self._icon_size * 0.32
            p.save()
            p.setBrush(QBrush(fg))
            p.setPen(Qt.PenStyle.NoPen)
            if icon_char == '\u25b6':  # ▶ 右三角（收起方向）
                pts = [QPointF(start_x + sz, cy), QPointF(start_x - sz * 0.5, cy - sz * 0.866), QPointF(start_x - sz * 0.5, cy + sz * 0.866)]
                p.drawPolygon(*pts)
            elif icon_char == '\u25bc':  # ▼ 下三角（展开方向）
                pts = [QPointF(start_x, cy + sz * 0.5), QPointF(start_x - sz * 0.866, cy - sz * 0.5), QPointF(start_x + sz * 0.866, cy - sz * 0.5)]
                p.drawPolygon(*pts)
            elif icon_char == '+':
                w = sz * 0.3
                p.drawRect(QRectF(start_x + sz * 0.3 - w, cy - sz, w * 2, sz * 2))
                p.drawRect(QRectF(start_x + sz * 0.3 - sz, cy - w, sz * 2, w * 2))
            p.restore()
            p.setFont(fl)
            p.drawText(QRectF(start_x + icon_w + gap, r.top(), label_w, r.height()), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label_part)
        else:
            p.setPen(QPen(fg))
            f = QFont(FONT_FAMILY, self._font_size); f.setBold(self._bold)
            p.setFont(f); p.drawText(r, Qt.AlignmentFlag.AlignCenter, self._text)


class SoftButton(CustomButton):
    def __init__(self, text="", bg="#e8f0ff", fg="#1e293b", parent=None,
                 font_size=13, height=36, disabled=False, radius=6):
        super().__init__(text, bg=bg, fg=fg, parent=parent,
                         font_size=font_size, height=height, disabled=disabled, radius=radius)
        self._hover_bg = QColor(bg).darker(105); self._bg = QColor(bg); self._current_bg = self._bg


class CheckBox(QCheckBox):
    """自绘复选框：文字在左、方块在右（按钮样式的勾选框）。
    勾选时方块中间手绘白色✓，解决部分环境下系统勾选符号不显示的问题。"""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # 复选框小方块（16x16 圆角，画在右侧）
        s = 16
        box = QRectF(self.width() - s - 1, (self.height() - s) / 2, s, s)
        if self.isChecked():
            p.setBrush(QBrush(QColor("#165dff")))
            p.setPen(QPen(QColor("#165dff"), 1))
        else:
            p.setBrush(QBrush(QColor("#ffffff")))
            p.setPen(QPen(QColor("#d6ddf2"), 1))
        p.drawRoundedRect(box, 3, 3)
        # 勾选时手绘 ✓（白色对勾）
        if self.isChecked():
            pen = QPen(QColor("#ffffff"), 2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            pts = QPolygonF([
                QPointF(box.left() + 3.5, box.top() + 8.0),
                QPointF(box.left() + 7.0, box.top() + 11.5),
                QPointF(box.left() + 12.5, box.top() + 4.5),
            ])
            p.drawPolyline(pts)
        # 文字（微软雅黑 13px，灰黑，右对齐紧贴方块左侧）
        p.setPen(QPen(QColor("#4e5969")))
        f = self.font()
        f.setFamily(FONT_FAMILY)
        f.setPixelSize(13)
        p.setFont(f)
        p.drawText(QRectF(0, 0, self.width() - s - 6, self.height()),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, self.text())
        p.end()


class StyledCheckBox(QCheckBox):
    """自绘复选框（一键导入商品信息同款）：方块在左、文字在右，勾选时蓝色方块+白色对勾，完全控制每一个像素"""

    BOX_SIZE = 14
    BOX_RADIUS = 0
    TEXT_GAP = 8
    PAD_V = 3
    PAD_H = 4

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._hover = False
        self.setMouseTracking(True)
        self.setMinimumHeight(self.BOX_SIZE + self.PAD_V * 2)

    def sizeHint(self):
        fm = self.fontMetrics()
        text_w = fm.horizontalAdvance(self.text())
        w = self.PAD_H * 2 + self.BOX_SIZE + self.TEXT_GAP + text_w
        h = max(self.BOX_SIZE + self.PAD_V * 2, fm.height() + self.PAD_V * 2)
        return QSize(w, h)

    def enterEvent(self, e):
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        rect = self.rect()
        box_x = self.PAD_H
        box_y = (rect.height() - self.BOX_SIZE) // 2
        text_x = box_x + self.BOX_SIZE + self.TEXT_GAP

        checked = self.isChecked()
        hover = self._hover

        if checked:
            bg_color = QColor("#4e83fd") if hover else QColor("#3370ff")
            border_color = bg_color
        else:
            bg_color = QColor("#ffffff")
            border_color = QColor("#4e83fd") if hover else QColor("#c9cdd4")

        box_rect = QRect(box_x, box_y, self.BOX_SIZE, self.BOX_SIZE)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(bg_color))
        p.drawRoundedRect(box_rect, self.BOX_RADIUS, self.BOX_RADIUS)

        pen = QPen(border_color)
        pen.setWidthF(1.5)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(box_rect, self.BOX_RADIUS, self.BOX_RADIUS)

        if checked:
            pen = QPen(QColor("#ffffff"))
            pen.setWidthF(1.8)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)

            cx = box_x + self.BOX_SIZE / 2
            cy = box_y + self.BOX_SIZE / 2
            p1_x, p1_y = cx - 3.5, cy + 0.5
            p2_x, p2_y = cx - 1,   cy + 3
            p3_x, p3_y = cx + 4,   cy - 3

            path = QPainterPath()
            path.moveTo(p1_x, p1_y)
            path.lineTo(p2_x, p2_y)
            path.lineTo(p3_x, p3_y)
            p.drawPath(path)

        p.setPen(QPen(QColor("#1d2129")))
        font = QFont(FONT_FAMILY)
        font.setPointSize(10)
        p.setFont(font)
        text_rect = QRect(text_x, 0, rect.width() - text_x - self.PAD_H, rect.height())
        p.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())

        p.end()


class PainterTextLabel(QWidget):
    """自绘文字控件：QPainter 手绘微软雅黑文字，彻底避免样式表字体解析回退问题。
    支持换行、颜色、字号、加粗、对齐；高度按内容自动计算。"""

    def __init__(self, text="", color="#334155", font_size=12, bold=False,
                 align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, word_wrap=True, parent=None):
        super().__init__(parent)
        self._text = text
        self._color = QColor(color)
        self._font_size = font_size
        self._bold = bold
        self._align = align
        self._word_wrap = word_wrap
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self._update_metrics()

    def setText(self, text):
        self._text = text
        self._update_metrics()
        self.updateGeometry()
        self.update()

    def text(self):
        return self._text

    def _update_metrics(self):
        # 锁定最小高度（按内容换行估算 + 上下留白），防止布局压缩导致文字被裁
        self.setMinimumHeight(self._calc_height(self.width() or 300))

    def _make_font(self):
        f = QFont(FONT_FAMILY, self._font_size)
        f.setBold(self._bold)
        return f

    def _calc_height(self, w):
        fm = QFontMetrics(self._make_font())
        w = max(w, 1)
        lines = 0
        for para in (self._text or '').split('\n'):
            if not para:
                lines += 1
                continue
            lines += max(1, (fm.horizontalAdvance(para) + w - 1) // w)
        return fm.height() * lines + 8

    def sizeHint(self):
        return QSize(100, self._calc_height(self.width() or 300))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_metrics()  # 宽度变化后换行数变化，重新锁高度并通知布局
        self.updateGeometry()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setFont(self._make_font())
        p.setPen(QPen(self._color))
        flags = int(self._align)
        if self._word_wrap:
            flags |= Qt.TextFlag.TextWordWrap
        p.drawText(self.rect(), flags, self._text or '')
        p.end()


class OverlayContainer(QWidget):
    """店铺容器：同一时刻只显示一个店铺，切到谁显示谁、其余隐藏。
    不再多店叠放抢 Z 序（Windows 下叠放外部窗口层级脆弱、且延迟对象盖后开的店），
    改用"只显示当前、其余藏起"，从根上没有 Z 序可抢，也就不会盖来盖去。
    后台店铺隐藏后照常运行（浏览器对隐藏页不冻结）。"""
    currentChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tabs = []      # 所有子标签页列表
        self._current = -1   # 当前显示的子标签页索引（-1=还没有标签页）

    def addWidget(self, w):
        w.setParent(self)
        self._tabs.append(w)
        self._update_geometry(w)
        if self._current < 0:
            # 首个店铺直接显示，代表当前
            w.show()
            self._current = 0
        else:
            # 新店先藏起来（不叠放、不抢 Z 序），当前店铺保持显示
            w.hide()
        return len(self._tabs) - 1

    def setCurrentIndex(self, idx):
        if idx < 0 or idx >= len(self._tabs) or idx == self._current:
            return
        # 先显示新的、再隐藏旧的：避免中间出现空白帧导致切换闪烁
        try:
            self._tabs[idx].show()
        except Exception:
            pass
        old = self._current
        self._current = idx
        try:
            self._tabs[old].hide()
        except Exception:
            pass
        self.currentChanged.emit(idx)

    def currentWidget(self):
        return self._tabs[self._current] if 0 <= self._current < len(self._tabs) else None

    def currentIndex(self):
        return self._current

    def indexOf(self, w):
        try:
            return self._tabs.index(w)
        except ValueError:
            return -1

    def count(self):
        return len(self._tabs)

    def widget(self, idx):
        return self._tabs[idx] if 0 <= idx < len(self._tabs) else None

    def removeWidget(self, w):
        if w in self._tabs:
            idx = self._tabs.index(w)
            self._tabs.remove(w)
            if self._current >= len(self._tabs):
                self._current = len(self._tabs) - 1
            w.setParent(None)
            # 若删掉的是当前店铺，则把新的"当前"显示出来（其余保持隐藏）
            if idx == self._current and self._tabs:
                try:
                    self._tabs[self._current].show()
                except Exception:
                    pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        r = self.rect()
        for t in self._tabs:
            t.setGeometry(r)

    def _update_geometry(self, w):
        w.setGeometry(self.rect())


# ── 按钮工厂函数 ──
def mk_primary_btn(text="", parent=None):
    return SoftButton(text, bg="#bfdbfe", fg="#1e293b", parent=parent)

def mk_secondary_btn(text="", parent=None):
    return CustomButton(text, bg="#d1d5db", fg="#374151", parent=parent)

def mk_danger_btn(text="", parent=None):
    return CustomButton(text, bg="#ef4444", fg="#ffffff", parent=parent)

def mk_primary_btn_large(text="", parent=None):
    return SoftButton(text, bg="#bfdbfe", fg="#1e293b", parent=parent, height=40)

def mk_outline_btn(text="", parent=None):
    return CustomButton(text, bg="#e5e7eb", fg="#374151", parent=parent)


class ShopTabBar(QTabBar):
    """店铺顶部标签栏（线式滑动款）：标签文字与滑动指示线都用同一套坐标自绘，
    保证线和店铺名文字天然居中；选中蓝字、未选中灰字、悬停变深；多了横向滚动。
    程序侧切换标签后要调 sync_indicator() 让指示线跟上（currentChanged 被屏蔽时用）。"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setExpanding(False)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)  # 横向只取内容宽度，不撑满顶栏，＋按钮才能紧挨店铺名
        # 关闭"始终预留翻页箭头空间"，避免标签不多时空出一大段空白把＋顶远
        self.setDrawBase(False)
        self.setElideMode(Qt.TextElideMode.ElideNone)  # 店铺名不省略，完整显示
        self.setFont(QFont(FONT_FAMILY, 10))  # 与标签字号一致，供宽度/指示线计算
        self._hover_index = -1   # 当前鼠标悬停的标签索引
        self.setMouseTracking(True)  # 无按键也跟踪鼠标移动（hover 变色）
        self._hide_indicator = False  # 批量登录期间隐藏指示线，避免轨迹条乱窜
        self._ind_x = 0.0   # 指示线当前中心x（动画插值）
        self._ind_w = 0.0   # 指示线当前宽度
        self._from_x = 0.0; self._to_x = 0.0
        self._from_w = 0.0; self._to_w = 0.0
        self._anim_start = 0.0
        self._anim_dur = 0.18  # 滑动动画时长（秒）
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(16)  # ~60fps
        self._anim_timer.timeout.connect(self._anim_tick)
        self.currentChanged.connect(self._on_current_changed)

    def sizeHint(self):
        # 只按店铺名实际宽度取尺寸，不预留多余空白，＋按钮才能紧贴店铺名
        w = 0
        for i in range(self.count()):
            r = self.tabRect(i)
            if not r.isNull():
                w += r.width()
        return QSize(w, self.height() or 36)

    def minimumSizeHint(self):
        # 连"最小宽度"也按店铺名实际宽度算，防止标签栏空出一截把＋顶远
        return self.sizeHint()

    def mouseMoveEvent(self, e):
        idx = self.tabAt(e.pos())
        if idx != self._hover_index:
            self._hover_index = idx
            self.update()
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        self._hover_index = -1
        self.update()
        super().leaveEvent(e)

    def setIndicatorHidden(self, hidden):
        """批量登录期间隐藏指示线，结束后显示（避免轨迹条乱窜）"""
        self._hide_indicator = bool(hidden)
        self.update()

    def _text_layout(self, text):
        """用底层排版（QTextLayout）生成文字布局，boundingRect 为精确真实边界"""
        layout = QTextLayout(text, QFont(FONT_FAMILY, 10))
        layout.beginLayout()
        line = layout.createLine()
        line.setLineWidth(1e9)  # 足够宽，单行不折
        layout.endLayout()
        return layout

    def _target(self):
        """当前选中标签的指示线目标（中心x=标签中心, 宽度=文字真实外框宽度），无选中返回 None"""
        idx = self.currentIndex()
        if idx < 0:
            return None
        r = self.tabRect(idx)
        if r.isNull():
            return None
        text = self.tabText(idx) or ''
        br = self._text_layout(text).boundingRect()
        # 指示线宽度=整个标签框宽度（文字+左右内边距），两端正好落在相邻竖线位置，间距统一
        # 中心用"左边缘+宽度/2"算精确小数（QRect.center()整数取整，偶数宽度会偏左1px）
        return r.left() + r.width() / 2.0, max(r.width(), 8)

    def showEvent(self, e):
        super().showEvent(e)
        # 首次显示：指示线直接落在当前标签，不做滑动动画
        if self._ind_w <= 0 and self.count():
            t = self._target()
            if t:
                self._ind_x, self._ind_w = t
                self._anim_timer.stop()
                self.update()

    def _on_current_changed(self, idx):
        if idx < 0:
            return
        t = self._target()
        if not t:
            return
        tx, tw = t
        if self._ind_w <= 0:
            # 还没画过线：直接跳过去
            self._ind_x, self._ind_w = tx, tw
            self.update()
            return
        self._from_x, self._from_w = self._ind_x, self._ind_w
        self._to_x, self._to_w = tx, tw
        self._anim_start = time.monotonic()
        self._anim_timer.start()

    def sync_indicator(self):
        """程序侧切换标签后调用：让指示线滑动到当前选中标签（不受信号屏蔽影响）。"""
        self._on_current_changed(self.currentIndex())

    def _anim_tick(self):
        t = (time.monotonic() - self._anim_start) / self._anim_dur
        if t >= 1:
            t = 1
            self._anim_timer.stop()
        ease = 1 - (1 - t) ** 3  # easeOutCubic：先快后慢
        self._ind_x = self._from_x + (self._to_x - self._from_x) * ease
        self._ind_w = self._from_w + (self._to_w - self._from_w) * ease
        self.update()

    def paintEvent(self, e):
        """自绘：店铺名用底层排版（QTextLayout）精确绘制，指示线跟随其真实边界，保证对齐。"""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cur = self.currentIndex()
        line_cx = None  # 选中文字真实边界中心（线和它同源）
        line_w = None   # 选中文字真实边界宽度
        n = self.count()
        for i in range(n):
            r = self.tabRect(i)
            if r.isNull():
                continue
            # 店铺标签之间用浅灰细竖线隔开（第2个起，画在各自左边界；高度16px垂直居中，同款样式）
            # 最后一个标签的右边界也画一条（＋号前的分隔线），与标签间竖线同一套坐标，保证与指示线贴合
            line_y = (self.height() - 16) / 2.0
            p.setPen(QPen(QColor("#e5e7eb"), 1))
            if i > 0:
                p.drawLine(QPointF(r.left(), line_y), QPointF(r.left(), line_y + 16))
            if i == n - 1:
                end_x = r.left() + r.width()
                p.drawLine(QPointF(end_x, line_y), QPointF(end_x, line_y + 16))
            text = self.tabText(i)
            if not text:
                continue
            layout = self._text_layout(text)
            br = layout.boundingRect()
            # 文字真实边界：水平用精确中心（左边缘+宽度/2，避免整数取整偏左），垂直相对整个标签栏高度居中后整体上移2像素
            cx_exact = r.left() + r.width() / 2.0
            x = cx_exact - br.width() / 2.0 - br.left()
            y = self.height() / 2.0 - br.height() / 2.0 - br.top() - 2
            if i == cur:
                color = QColor("#2563eb")
            elif i == self._hover_index:
                color = QColor("#1f2937")
            else:
                color = QColor("#6b7280")
            p.setPen(QPen(color))
            p.setBrush(Qt.BrushStyle.NoBrush)
            layout.draw(p, QPointF(x, y))
            if i == cur:
                line_cx = cx_exact  # 与文字同一精确中心（整数中心偶数宽度会偏左1px）
                # 与 _target() 同源：指示线宽度=整个标签框宽度，两端正好落在相邻竖线位置
                line_w = max(r.width(), 8)
        # 2) 滑动指示线：批量登录期间隐藏；动画进行中取插值（平滑滑动）；静止时直接用当前选中文字的同源中心，保证对齐
        if line_cx is not None and line_w is not None and not self._hide_indicator:
            if self._anim_timer.isActive():
                cx = self._ind_x
                w = max(self._ind_w, 8)
            else:
                cx = line_cx
                w = line_w
            line_h = 3
            y = self.height() - line_h - 3
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#2563eb"))
            p.drawRoundedRect(QRectF(cx - w / 2, y, w, line_h), line_h / 2, line_h / 2)
        p.end()


class WinButton(QPushButton):
    """自绘窗口控制按钮：最小化/最大化/关闭/加号。
    - 最小化/最大化/关闭：标准 Windows 标题栏风格，深灰细线图标，无悬停背景，简洁。
      最大化时调 setMaximized(True) 切换为"还原"图标（两个叠放方框）。
    - 加号：保持与顶部店铺标签同款（灰→悬停深灰，无背景）。
    kind: 'min'/'max'/'close'/'plus'"""
    def __init__(self, kind, parent=None, height=42, width=46):
        super().__init__(parent)
        self._kind = kind
        self._is_max = False
        self._hover = False
        self.setFixedSize(width, height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("")

    def setMaximized(self, is_max):
        """最大化状态：True 显示"还原"图标，False 显示"最大化"图标"""
        self._is_max = bool(is_max)
        self.update()

    def enterEvent(self, e):
        self._hover = True; self.update(); super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False; self.update(); super().leaveEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2.0, h / 2.0

        # 加号：与顶部店铺标签同款（灰→悬停深灰，无背景）
        if self._kind == 'plus':
            s = h * 0.30
            c = QColor("#1f2937") if self._hover else QColor("#6b7280")
            p.setPen(QPen(c, 1.0)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawLine(QPointF(cx - s, cy), QPointF(cx + s, cy))
            p.drawLine(QPointF(cx, cy - s), QPointF(cx, cy + s))
            p.end(); return

        # 最小化/最大化/关闭：标准 Windows 标题栏风格，深灰细线图标，无背景
        icon_color = QColor("#1f2937") if self._hover else QColor("#374151")
        p.setPen(QPen(icon_color, 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        # 图标用固定像素尺寸，保证 28x30 按钮下不变形、居中
        size = 10  # 主图标区域 10x10
        x0, y0 = cx - size / 2.0, cy - size / 2.0
        if self._kind == 'min':
            # 最小化：一条 10x1 的横线，放在中下方
            y_line = cy + size / 2.0 - 1
            p.drawLine(QPointF(cx - size / 2.0, y_line), QPointF(cx + size / 2.0, y_line))
        elif self._kind == 'max':
            if self._is_max:
                # 还原：两个 8x8 方框交叠 3px（前框左上、后框右下）
                box = 8
                off = 3
                # 后框（右下）
                p.drawRect(QRectF(x0 + off, y0 + off, box, box))
                # 前框（左上）用背景色填充，盖住交叠部分
                p.fillRect(QRectF(x0, y0, box, box), QColor("#ffffff"))
                p.drawRect(QRectF(x0, y0, box, box))
            else:
                # 最大化：10x10 空心方框
                p.drawRect(QRectF(x0, y0, size, size))
        elif self._kind == 'close':
            # 关闭：等臂 X，10x10 区域
            d = size / 2.0 - 0.5
            p.setPen(QPen(icon_color, 1.3))
            p.drawLine(QPointF(cx - d, cy - d), QPointF(cx + d, cy + d))
            p.drawLine(QPointF(cx - d, cy + d), QPointF(cx + d, cy - d))
        p.end()


class ShopTextButton(QPushButton):
    """自绘文字按钮：用 QTextLayout 绘制文字（与 ShopTabBar 店铺标签 1:1 同款渲染），
    灰色文字、鼠标悬停变深、无背景、无图标。用于顶栏与店铺标签同款样式的文字按钮。"""
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._text = text
        self._hover = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("")

    def setText(self, t):
        self._text = t
        self.update()

    def text(self):
        return self._text

    def enterEvent(self, e):
        self._hover = True; self.update(); super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False; self.update(); super().leaveEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        layout = QTextLayout(self._text, QFont(FONT_FAMILY, 10))
        layout.beginLayout()
        line = layout.createLine()
        line.setLineWidth(1e9)
        layout.endLayout()
        br = layout.boundingRect()
        color = QColor("#1f2937") if self._hover else QColor("#6b7280")
        x = self.rect().center().x() - br.width() / 2.0 - br.left()
        y = self.rect().center().y() - br.height() / 2.0 - br.top()
        p.setPen(QPen(color))
        p.setBrush(Qt.BrushStyle.NoBrush)
        layout.draw(p, QPointF(x, y))
        p.end()

    def sizeHint(self):
        fm = QFontMetrics(QFont(FONT_FAMILY, 10))
        br = fm.boundingRect(self._text)
        return QSize(int(br.width()) + 32, 26)


class _SideTip(QLabel):
    """侧边栏专用悬浮提示气泡：白底圆角卡片（不挂阴影特效，避免缓存渲染显示旧文字）。
    全局共用一个实例（不抢焦点、不挡鼠标），显示在按钮右侧垂直居中。"""
    _inst = None

    @classmethod
    def _get(cls):
        if cls._inst is None:
            cls._inst = cls()
        return cls._inst

    def __init__(self):
        super().__init__(None, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)  # 不挡鼠标，离开按钮即消失
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)     # 圆角外透明
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)     # 不抢主窗口焦点
        # 注意：不挂 QGraphicsDropShadowEffect——特效走缓存渲染，快速切换文字时
        # 屏幕上会残留上一条的旧画面（显示错文字的元凶），自绘提示的标准做法是不挂特效
        # 延迟隐藏定时器挂在气泡自己身上（全程序只有一个气泡、一个定时器）：
        # 离开按钮后稍等再隐藏，划到别的按钮时取消的是同一个定时器，不会出现"别人的定时器把气泡藏了"
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def cancel_hide(self):
        """取消还没生效的延迟隐藏（鼠标划到任一按钮时调用）"""
        self._hide_timer.stop()

    def schedule_hide(self, ms=120):
        """安排延迟隐藏：鼠标离开侧边栏按钮后稍等片刻再隐藏"""
        self._hide_timer.start(ms)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # 白底圆角卡片（边缘留 0.5px 给描边线，不超出窗口）
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        p.setPen(QPen(QColor('#e0e4ed'), 1))
        p.setBrush(QColor('#ffffff'))
        p.drawRoundedRect(r, 6, 6)
        p.setPen(QPen(QColor('#1f2937')))
        p.setFont(QFont(FONT_FAMILY, 10))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())
        p.end()


class StatusDotLabel(QWidget):
    """状态圆点+文字标签（顶栏左上角接待状态用）：
    圆点和文字由同一支画笔绘制、同一个垂直居中标准，保证对齐（富文本符号基线不齐）。"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._text = ''
        self._dot_color = QColor('#22c55e')
        self._text_color = QColor('#165dff')
        self.setFixedHeight(36)
        self.setStyleSheet('background: transparent;')

    def set_status(self, text, dot_color, text_color):
        """更新状态文字与颜色（宽高按文字自适应）"""
        self._text = text
        self._dot_color = QColor(dot_color)
        self._text_color = QColor(text_color)
        self.setFixedWidth(QFontMetrics(QFont(FONT_FAMILY, 10)).horizontalAdvance(text) + 34)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        h = self.height()
        # 圆点：直径8，垂直居中
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._dot_color)
        p.drawEllipse(QRectF(4, h / 2 - 4, 8, 8))
        # 文字：与圆点同一水平线，垂直居中
        p.setPen(QPen(self._text_color))
        p.setFont(QFont(FONT_FAMILY, 10, QFont.Weight.Bold))
        p.drawText(QRectF(18, 0, self.width() - 18, h),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._text)
        p.end()


class SideBarButton(QPushButton):
    """自绘侧边栏按钮：只显示居中图片图标，不显示文字；功能名通过鼠标悬浮提示展示。
    - 悬停：浅灰底；选中（active）：淡蓝底、图标滤镜高亮为品牌蓝。
    - 支持动态更新提示文字（自动回复状态 / 静音状态），改文字即改悬浮提示。
    icon_path: 图片图标的绝对/相对路径（为空则不画图标）。"""
    def __init__(self, text="", icon_path=None, active=False, parent=None, height=40, icon_size=22, keep_original_color=False):
        super().__init__(parent)
        self._text = text
        self._icon_path = icon_path
        self._icon_size = icon_size
        self._active = bool(active)
        self._hover = False
        self._keep_original_color = bool(keep_original_color)  # True = 保留图片本色，不做变色处理
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(height)
        self.setStyleSheet("")
        # 悬浮提示用自绘气泡（_SideTip），不用系统 setToolTip（Windows 上是黑框）
        # 延迟隐藏定时器在气泡 _SideTip 身上（全局唯一），见 cancel_hide/schedule_hide

    def setText(self, t):
        self._text = t
        self.update()

    def text(self):
        return self._text

    def setActive(self, active):
        self._active = bool(active)
        self.update()

    def setIconPath(self, icon_path):
        self._icon_path = icon_path
        self.update()

    def enterEvent(self, e):
        self._hover = True; self.update()
        # 悬浮显示自绘提示气泡：按钮右侧、垂直居中（文字为当前功能名/状态名）
        if self._text:
            tip = _SideTip._get()
            tip.cancel_hide()  # 取消还没生效的延迟隐藏（同一个定时器，谁被划到谁取消）
            tip.setText(self._text)
            tip.setFixedHeight(32)
            tip.setFixedWidth(QFontMetrics(QFont(FONT_FAMILY, 10)).horizontalAdvance(self._text) + 40)
            gp = self.mapToGlobal(QPoint(self.width() + 8, (self.height() - 32) // 2))
            tip.move(gp)
            tip.show()
            tip.repaint()  # 每次都同步重画：不依赖异步刷新，杜绝旧画面残留
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False; self.update()
        if self._text:
            _SideTip._get().schedule_hide(120)  # 延迟隐藏：快速划到别的按钮时由对方取消
        super().leaveEvent(e)

    def sizeHint(self):
        # 只显示图标：按钮宽度按图标尺寸给个固定建议值
        return QSize(48, self.height())

    # 图标变色缓存：路径 -> 变黑后的图（避免每次重画都做变色处理）
    _BLACK_ICON_CACHE = {}

    @classmethod
    def _black_icon(cls, icon_path):
        """把图标统一染成黑色：保留线条的透明度（抗锯齿边缘平滑），图片文件本身不动。"""
        if icon_path in cls._BLACK_ICON_CACHE:
            return cls._BLACK_ICON_CACHE[icon_path]
        src = QPixmap(icon_path)
        if src.isNull():
            return src
        out = QPixmap(src.size())
        out.fill(Qt.GlobalColor.transparent)
        p = QPainter(out)
        p.drawPixmap(0, 0, src)
        # 仅在"有像素"的地方涂黑，透明部分保持透明 → 蓝线/红线都变成黑线
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        p.fillRect(src.rect(), QColor("#555555"))
        p.end()
        cls._BLACK_ICON_CACHE[icon_path] = out
        return out

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # 背景：悬停浅灰 / 选中淡蓝
        if self._active:
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("#e8f4ff"))
            p.drawRoundedRect(QRectF(2, 2, w - 4, h - 4), 8, 8)
        elif self._hover:
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("#f5f6f8"))
            p.drawRoundedRect(QRectF(2, 2, w - 4, h - 4), 8, 8)

        # 居中图片图标：按 _icon_size 等比例缩放，水平垂直都居中（不画文字，功能名走悬浮提示）
        icon_size = self._icon_size
        if self._icon_path and os.path.exists(self._icon_path):
            pm = QPixmap(self._icon_path) if self._keep_original_color else self._black_icon(self._icon_path)
            if not pm.isNull() and pm.width() > 0 and pm.height() > 0:
                w_icon = max(1, int(round(pm.width() * icon_size / max(1, pm.height()))))
                pm = pm.scaled(w_icon, icon_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                p.drawPixmap(int((w - w_icon) / 2.0), int((h - icon_size) / 2.0), pm)
        p.end()
