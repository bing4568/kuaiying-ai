from fire_browser.main_window._deps import *

class _Menu:
    # 主窗口零件：@menu（方法来自 main_qt.py 的 FireBrowser，按功能归位，非新增逻辑）

    def _show_contact(self):
        """联系我们弹窗：显示微信号并支持一键复制"""
        WEIXIN_ID = "18983614919"

        # 外层透明窗口（四周留白承载阴影，与人工弹窗一致的阴影方案）
        dlg = QDialog(self)
        dlg.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        dlg.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        dlg.setFixedSize(500, 388)

        outer = QVBoxLayout(dlg)
        outer.setContentsMargins(40, 40, 40, 40)

        # 白色圆角卡片
        card = QFrame()
        card.setFixedSize(420, 308)
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 16px;
            }
        """)
        outer.addWidget(card)

        # 阴影效果（与人工弹窗一致的参数）
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(60)
        shadow.setXOffset(0)
        shadow.setYOffset(16)
        shadow.setColor(QColor(30, 58, 138, 50))
        card.setGraphicsEffect(shadow)

        inner = QVBoxLayout(card)
        inner.setContentsMargins(30, 27, 30, 27)
        inner.setSpacing(15)

        title = QLabel("添加管理员微信")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-family: 'Microsoft YaHei'; color: #1f2937; font-size: 24px; font-weight: bold; border: none;")
        inner.addWidget(title)

        tip = QLabel("如有任何使用或配置疑问\n欢迎随时联系管理员。也可以协助完成配置")
        tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tip.setWordWrap(True)
        tip.setStyleSheet("font-family: 'Microsoft YaHei'; color: #6b7280; font-size: 18px; border: none;")
        inner.addWidget(tip)

        wx_label = QLabel(WEIXIN_ID)
        wx_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wx_label.setStyleSheet("font-family: 'Microsoft YaHei'; color: #1d4ed8; font-size: 33px; font-weight: bold; border: none;")
        inner.addWidget(wx_label)

        copy_btn = QPushButton("复制微信号")
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.setFixedHeight(54)
        copy_btn.setStyleSheet("""
            QPushButton {
                background: #2563eb;
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 21px;
                font-family: 'Microsoft YaHei';
            }
            QPushButton:hover { background: #1d4ed8; }
            QPushButton:pressed { background: #1e40af; }
        """)
        inner.addWidget(copy_btn)

        def do_copy():
            QApplication.clipboard().setText(WEIXIN_ID)
            copy_btn.setText("已复制 ✓")
            QTimer.singleShot(1500, lambda: copy_btn.setText("复制微信号"))

        copy_btn.clicked.connect(do_copy)

        # 右上角关闭按钮（无边框对话框没有系统关闭按钮，需自绘）
        close_btn = QPushButton("×", dlg)
        close_btn.setFixedSize(36, 36)
        close_btn.move(40 + 420 - 36 - 10, 40 + 10)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #9ca3af;
                border: none;
                border-radius: 18px;
                font-size: 20px;
                font-family: 'Microsoft YaHei';
            }
            QPushButton:hover { background: rgba(239,68,68,0.15); color: #ef4444; }
        """)
        close_btn.clicked.connect(dlg.close)

        # 居中显示在主窗口上
        main = self.window()
        if main is not None:
            c = main.frameGeometry().center()
            dlg.move(c.x() - dlg.width() // 2, c.y() - dlg.height() // 2)

        dlg.exec()

    def _raise_main_window(self):
        """设置中心等全屏页关闭后，把主窗口顶回前台（防止前台身份被其他程序窗口抢走）"""
        try:
            if self.isMinimized():
                self.showNormal()
            self.show()
            self.raise_()
            self.activateWindow()
        except Exception:
            pass

    def _refresh_shops(self):
        self._shop_mgr._refresh_shops()

    def _store_context_menu(self, pos):
        self._shop_mgr._store_context_menu(pos)

    def _show_shop_list_menu(self):
        """加号点击：弹出居中的"店铺列表"弹窗（白卡圆角+阴影样式）。
        标题"店铺列表"+右上角关闭；中间店铺列表（每行店铺名+启动/运行状态，右键编辑/删除）；
        底部一键启动/添加店铺。打开时按当前状态重建。"""
        dlg = QDialog(self)
        dlg.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        dlg.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        # 外层容器：圆角白色卡片
        card = QWidget(dlg)
        card.setObjectName("card")
        card.setMinimumWidth(300)

        outer = QVBoxLayout(dlg)
        outer.setContentsMargins(40, 40, 40, 40)
        outer.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 24, 28, 24)
        card_layout.setSpacing(16)

        # 标题行：蓝色标题 + 右上角关闭按钮
        header = QHBoxLayout()
        header.setSpacing(0)
        title = QLabel("店铺列表")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #2563eb;")
        header.addWidget(title)
        header.addStretch(1)
        btn_close = WinButton('close', height=21, width=23)
        btn_close.setToolTip("关闭")
        btn_close.clicked.connect(dlg.close)
        header.addWidget(btn_close)
        card_layout.addLayout(header)

        # 店铺列表（每行店铺名+启动/运行状态；右键编辑/删除）
        shop_list = QListWidget()
        shop_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        def _popup_shop_menu(pos):
            item = shop_list.itemAt(pos)
            if not item:
                return
            shop = item.data(Qt.ItemDataRole.UserRole)
            if not shop:
                return
            menu = QMenu(self)
            menu.addAction("编辑店铺", lambda: (dlg.close(), self._shop_mgr._edit_shop(shop)))
            menu.addAction("删除店铺", lambda: (dlg.close(), self._shop_mgr._delete_shop(shop)))
            menu.exec(shop_list.viewport().mapToGlobal(pos))
        shop_list.customContextMenuRequested.connect(_popup_shop_menu)
        shop_list.setStyleSheet("""
            QListWidget { border: none; font-size: 13px; outline: none; background: transparent; }
            QListWidget::item { padding: 0px; border: none; }
            QListWidget::item:hover { background: #f9fafb; }
        """ + SCROLLBAR_STYLE)
        self._shop_mgr._fill_shop_list(shop_list)
        self._shop_mgr._shop_list_widget = shop_list  # 记录列表控件，供启动/保存后刷新状态（不关弹窗）
        shop_list.setFixedHeight(300)  # 固定高度，店铺多时内部滚动
        card_layout.addWidget(shop_list)

        # 底部：一键启动 + 添加店铺（上下排列，同以前左侧店铺列表）
        bar = QVBoxLayout()
        bar.setSpacing(10)
        btn_start_all = _SoftButton("▶ 一键启动", bg="#bfdbfe", fg="#1e293b", height=42, radius=10)
        btn_start_all.clicked.connect(lambda: (dlg.close(), self._on_start_all_clicked()))
        bar.addWidget(btn_start_all)
        btn_add = _CustomButton("+ 添加店铺", bg="#d1d5db", fg="#374151", height=42, radius=10)
        btn_add.clicked.connect(lambda: self._add_shop())
        bar.addWidget(btn_add)
        card_layout.addLayout(bar)

        # 阴影（白卡圆角）
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(60)
        shadow.setXOffset(0)
        shadow.setYOffset(16)
        shadow.setColor(QColor(30, 58, 138, 50))
        card.setGraphicsEffect(shadow)

        dlg.setStyleSheet("""
            #card {
                background-color: white;
                border-radius: 16px;
            }
        """)
        dlg.finished.connect(lambda: setattr(self._shop_mgr, '_shop_list_widget', None))  # 弹窗关闭时清空记录，避免刷新到已销毁控件
        dlg.show()  # 居中显示于主窗口

    def _add_shop(self):
        self._shop_mgr._add_shop()

    def _start_all(self):
        self._shop_mgr._start_all()

    def _on_start_all_clicked(self):
        """一键启动点击：直接启动全部店铺"""
        self._shop_mgr._start_all()

    def _update_start_all_empty_btn(self):
        """无已打开店铺时左上角显示"一键启动"按钮；有店铺标签后隐藏"""
        try:
            self._btn_start_all_empty.setVisible(self.shop_tabs.count() == 0)
        except Exception:
            pass
        self._update_ai_status_label()

    def _update_ai_status_label(self):
        """顶栏左上角接待状态：有店铺时显示（与"一键启动"互斥），文字随自动回复开关变化。
        开启→绿点+AI接待中（蓝字）；停止→灰点+停止接待（灰字）"""
        try:
            if not hasattr(self, '_ai_status_label'):
                return
            has_shop = self.shop_tabs.count() > 0
            self._ai_status_label.setVisible(has_shop)
            if has_shop:
                if getattr(self, 'monitoring', False):
                    self._ai_status_label.set_status('AI接待中', '#22c55e', '#165dff')
                else:
                    self._ai_status_label.set_status('停止接待', '#9aa4b2', '#6b7280')
        except Exception:
            pass

    def _launch_next_shop(self, index, shops):
        self._shop_mgr._launch_next_shop(index, shops)

    def _stop_all(self):
        self._shop_mgr._stop_all()
