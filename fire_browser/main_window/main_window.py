from fire_browser.main_window._deps import *
from fire_browser.main_window._frameless import _TitleBarDrag, _FramelessNccalcFilter

from fire_browser.main_window._login import _Login
from fire_browser.main_window._switch import _Switch
from fire_browser.main_window._menu import _Menu
from fire_browser.main_window._settings import _Settings
from fire_browser.main_window._mute import _Mute
from fire_browser.main_window._msgcenter import _MsgCenter
from fire_browser.main_window._lifecycle import _Lifecycle
from fire_browser.main_window._testpanel import _TestPanel

class FireBrowser(_Login, _Switch, _Menu, _Settings, _Mute, _MsgCenter, _Lifecycle, _TestPanel, QMainWindow):
    # 主窗口（拆分后外壳）：装配各零件 + 界面搭建 + 生命周期事件。方法来自 main_qt.py。

    def __init__(self):
        super().__init__()
        # 普通窗口（主流软件做法，对照 Chrome/Trae）：系统边框样式天生保留，阴影/贴边拉伸/
        # 窗口动画全部由系统原生负责；系统标题栏由 _FramelessNccalcFilter 拦 WM_NCCALCSIZE 抹掉。
        # 切勿改回 Qt.FramelessWindowHint——那是"无边框+事后补样式"的老路，Qt 重写样式时阴影和
        # 拉伸会随时消失（本项目反复踩坑的根源）。
        self.setWindowTitle("快应AI")
        self.setWindowIcon(QIcon(os.path.join(PROJECT_ROOT, 'icons', 'logo1.png')))
        # 窗口按屏幕可用区域的90%显示并居中，跟随屏幕实际像素自适应（适配不同电脑的分辨率）
        try:
            _geo = QApplication.primaryScreen().availableGeometry()
            _w = int(_geo.width() * 0.9)
            _h = int(_geo.height() * 0.9)
        except Exception:
            _w, _h = 1400, 900
        self.resize(_w, _h)
        self.move(_geo.x() + (_geo.width() - _w) // 2, _geo.y() + (_geo.height() - _h) // 2)
        self.setMinimumSize(int(_w * 0.7), int(_h * 0.7))
        self._frameless_hwnd = None  # 主窗口原生句柄（首次显示的 showEvent 里记录，供消息过滤器比对）
        self.stack = OverlayContainer()  # 叠放容器：所有店铺页面叠在一起，防止后台被浏览器限制
        self.stack.winId()  # 让容器一开始就作为底层原生窗口存在：首家店网页控件首次装入时不再重建主窗口骨架（否则界面会像刚启动一样重载一遍、已开弹窗被清掉），2026-08-29 修
        self.browser_tabs = {}  # {索引: BrowserTab} 所有打开的店铺标签页
        self._stack_names = {}  # idx -> shop_name
        self.monitoring = False  # 主开关：所有标签页跟着走
        # ── 测试模式（测试.bat 带参数拉起）：所有功能模块默认关闭，靠开关面板逐个打开定位卡死元凶 ──
        self._test_mode = '--testmode' in sys.argv
        self._test_switches = {name: False for name in _TEST_MODULES}
        self._browser_muted = self._load_mute_state()  # 浏览器静音状态
        self._filter_keywords = self._load_filter_keywords()  # 拦截关键词列表
        self._msg_center_file = os.path.join(_data_dir(), 'msg_center.json')  # 消息中心数据文件
        self._blocked_transfer_list = self._load_msg_center()  # 从文件加载消息中心数据
        self._init_db()
        from config_manager import ConfigManager
        ConfigManager.instance()  # 配置管家初始化：首启动迁移旧配置 + 缺键补默认（真落盘）
        self._shop_mgr = ShopManager(self)  # 店铺管理器
        self._nick_mgr = NicknameManager()  # 昵称管理器
        self._nick_mgr.clean_expired(90)
        self._setup_ui()
        # ── 消息日志对话框（已从右侧移入"更多功能"弹出查看）──
        self._msg_log_dialog = QDialog(self)
        self._msg_log_dialog.setWindowTitle("消息日志")
        self._msg_log_dialog.setWindowFlags(self._msg_log_dialog.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint | Qt.WindowType.WindowMinMaxButtonsHint)
        self._msg_log_dialog.resize(650, 600)
        msg_l = QVBoxLayout(self._msg_log_dialog)
        self.msg_log_text = QTextEdit()
        self.msg_log_text.setReadOnly(True)
        self.msg_log_text.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 11px; border: 1px solid #e5e7eb; border-radius: 4px; background: #fafbfc;")
        # 消息日志自动换行、不显示水平滚动条；垂直滚动条直接贴样式确保生效
        self.msg_log_text.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.msg_log_text.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.msg_log_text.verticalScrollBar().setStyleSheet(SCROLLBAR_STYLE)
        msg_l.addWidget(self.msg_log_text)
        # AI思考过程打字机已停用，不再显示思考内容，
        # 运行日志改为写入独立文件（data/run.log）。

        # ── 日志管理器 ──
        self._log_mgr = LogManager(
            msg_log_text=getattr(self, 'msg_log_text', None),
            diag_cb=_write_diag_file,  # 日志改写进诊断日志文件（诊断工具查看）
        )
        # 测试模式：消息日志面板渲染受"日志面板刷新"开关控制（非测试模式该开关恒为开，不影响正常使用）
        self._log_mgr.test_gate = lambda: self._test_on('日志面板刷新')
        # 运行日志线程安全：子线程日志入队，主线程定时统一写文件
        self._win_log_timer = QTimer(self)
        self._win_log_timer.timeout.connect(self._log_mgr.drain_window_logs)
        self._win_log_timer.start(200)
        # ── 加载店铺（LogManager 就绪后才能安全创建 BrowserTab）──
        self._refresh_shops()

        self._keepalive_timer = QTimer(self)
        self._keepalive_timer.timeout.connect(self._background_keepalive)
        self._keepalive_timer.start(60000)
        # 切换标签页时刷新消息处理
        self.stack.currentChanged.connect(self._on_tab_changed)
        # 系统托盘：叉掉最小化到托盘
        self._tray_icon = QSystemTrayIcon(QIcon(os.path.join(PROJECT_ROOT, 'icons', 'logo1.png')), self)
        self._tray_icon.setToolTip("快应AI")
        tray_menu = QMenu()
        tray_menu.addAction("显示窗口", self._show_from_tray)
        tray_menu.addSeparator()
        tray_menu.addAction("退出程序", self._real_quit)
        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.activated.connect(lambda reason: self._show_from_tray() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self._tray_icon.show()
        self._quitting = False  # 是否正在退出（防止重复退出弹窗）
        self._login_dlg = None  # 留一个引用：登录框弹起后记录，退出时一起关掉，保证一体退出
        # 共享待发送队列：所有标签页共用，key为纯数字uid
        # ── 心跳留痕：每3秒写一次"我还活着"，崩溃后凭此判断消失时刻 ──
        self._life_timer = QTimer(self)
        self._life_timer.timeout.connect(lambda: _write_life('心跳'))
        self._life_timer.start(3000)

        # ── 自动更新系统 ──
        from config_manager import ConfigManager as _CM
        _svr = _CM.instance().get('auth', 'server_url', fallback='')  # 更新服务器地址
        self._updater = Updater(LOCAL_VERSION, _DEBUG_MODE, server_url=_svr, parent=self)  # 自动更新管理器
        self._updater.status_changed.connect(self._on_update_status)
        self._updater.apply_ready.connect(self._real_quit)
        # 兼容旧信号连接（_start_update 已在 updater 中处理）
        self._start_update = self._updater._start_apply

        # 启动后 2 秒检查更新
        QTimer.singleShot(2000, self._check_update)

        # 安装信号 → 启动安装（两层保险之一）
        self._start_update.connect(self._apply_update)
    def _setup_ui(self):
        cw = QWidget(); self.setCentralWidget(cw)
        cw.setStyleSheet("""
            QWidget { background: #f5f6fa; font-family: 'Microsoft YaHei', 'PingFang SC'; }
            QMainWindow { background: #f5f6fa; }
        """)
        main_layout = QVBoxLayout(cw)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 中间层（顶栏以下）：左侧功能卡片 + 右侧页面区
        middle = QWidget()
        middle.setStyleSheet("background: transparent;")
        middle_l = QHBoxLayout(middle)
        middle_l.setContentsMargins(0, 0, 0, 0)
        middle_l.setSpacing(0)

        # ===== 右侧总列（页面区 + 底部状态）：左侧功能卡片单独占一列，整列参与挤压 =====
        right_col = QWidget()
        right_col.setStyleSheet("background: transparent;")
        right_l = QVBoxLayout(right_col)
        right_l.setContentsMargins(0, 0, 0, 0)
        right_l.setSpacing(0)

        # ===== 主内容区（页面区）=====
        content = QWidget()
        content_layout = QHBoxLayout(content)
        # 左边距 0：让左侧功能卡片贴边；店铺工作台页面的左右对称边距由下方容器各自保证
        content_layout.setContentsMargins(0, 8, 8, 8)
        content_layout.setSpacing(0)

        # 【左列】功能卡片：自动回复开关 + 各功能（图片图标+文字，白底圆角卡片）
        base_dir = PROJECT_ROOT
        def _icon(name):
            return os.path.join(base_dir, 'icons', name)

        left_panel = QWidget()
        left_panel.setFixedWidth(56)
        left_panel.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)  # 宽固定、高撑满整列
        left_panel.setStyleSheet("background: transparent;")
        # 左列内部左右排：细长折叠条 + 功能卡片
        left_l = QHBoxLayout(left_panel)
        left_l.setContentsMargins(0, 0, 0, 0)
        left_l.setSpacing(0)

        # 侧栏容器：透明背景（不要白底卡片），按钮直接浮在页面底色上
        card_side = QFrame()
        card_side.setStyleSheet("background: transparent; border: none;")
        # 卡片内部横向排布：左侧功能按钮列 + 右侧折叠窄条（窄条融进卡片，不单独放外面）
        card_l = QHBoxLayout(card_side)
        card_l.setContentsMargins(0, 0, 0, 0)
        card_l.setSpacing(0)

        # 按钮容器：竖排各功能按钮
        btn_box = QWidget()
        btn_box.setStyleSheet("background: transparent;")
        btn_l = QVBoxLayout(btn_box)
        btn_l.setContentsMargins(8, 8, 8, 8)
        btn_l.setSpacing(2)

        # 自动回复开关（运行态选中高亮；停止态显示"开启自动回复"，开启态显示"关闭自动回复"）
        self._btn_auto = SideBarButton("开启自动回复", icon_path=_icon('AI回复.png'), height=40, icon_size=26)
        self._btn_auto.clicked.connect(self._on_toggle_clicked)
        btn_l.addWidget(self._btn_auto)

        # 原“更多功能”菜单的各功能项，全部展开为独立按钮
        def _mk_func(icon_file, text, cb):
            b = SideBarButton(text, icon_path=_icon(icon_file), height=40)
            b.clicked.connect(cb)
            return b

        self._btn_mute = _mk_func('声音开启.png', "浏览器声音", self._toggle_mute)
        self._refresh_mute_button()  # 启动时按上次静音状态显示正确图标/文字
        btn_l.addWidget(_mk_func('消息中心.png', "消息中心", self._show_msg_center))
        btn_l.addWidget(_mk_func('黑名单.png', "黑名单", self._open_blacklist))
        btn_l.addWidget(self._btn_mute)
        btn_l.addWidget(_mk_func('消息中心.png', "消息日志", self._open_msg_log))

        # 弹性空隙：把下面两个按钮推到最底部（联系我们在上，设置中心在最底部）
        # 这两个按钮保留图标原色（不做变色处理）
        btn_l.addStretch()
        b_contact = SideBarButton("联系我们", icon_path=_icon('联系客服.png'), height=40, keep_original_color=True)
        b_contact.clicked.connect(self._show_contact)
        btn_l.addWidget(b_contact)
        b_settings = SideBarButton("设置中心", icon_path=_icon('设置.png'), height=40, keep_original_color=True)
        b_settings.clicked.connect(self._show_reply_settings)
        btn_l.addWidget(b_settings)
        card_l.addWidget(btn_box)

        # 左列只挂这一张卡片；加入中间层（顶栏以下），不再顶到窗口最上沿
        left_l.addWidget(card_side)

        middle_l.addWidget(left_panel)

        # 【中列】聊天主窗口（BrowserTab 标签页）
        center_panel = QWidget()
        center_panel.setStyleSheet("background: #fff; border-radius: 8px;")
        center_l = QVBoxLayout(center_panel)
        center_l.setContentsMargins(4, 4, 4, 4)
        center_l.addWidget(self.stack, 1)
        # 工作台卡片包一层左边距 8 的容器：让店铺工作台左右边距对称，不受左侧功能卡片贴边影响
        center_wrap = QWidget()
        center_wrap.setStyleSheet("background: transparent;")
        center_wrap_l = QHBoxLayout(center_wrap)
        center_wrap_l.setContentsMargins(8, 0, 0, 0)
        center_wrap_l.setSpacing(0)
        center_wrap_l.addWidget(center_panel, 1)
        content_layout.addWidget(center_wrap, 1)

        # ===== 顶部店铺标签栏（在页面区上方，整行横排；点标签打开/切换，多了横向滚动）=====
        top_bar = QWidget()
        top_bar.setStyleSheet("background: #fff;")
        top_bar.setFixedHeight(36)  # 固定高度：有店铺/无店铺顶栏都一样高
        top_bar.setMouseTracking(True)  # 顶栏悬停追踪：贴顶 6px 显示上下拉伸光标（配合 _TitleBarDrag）
        top_bar_l = QHBoxLayout(top_bar)
        top_bar_l.setContentsMargins(8, 0, 8, 0)
        top_bar_l.setSpacing(8)

        # 顶栏左上角AI接待状态：有店铺时显示、与"一键启动"互斥，文字随自动回复开关变化
        self._ai_status_label = StatusDotLabel()
        top_bar_l.addWidget(self._ai_status_label)

        # 无已打开店铺时：左上角显示"一键启动"按钮（自绘文字，与店铺标签 1:1 同款渲染；有店铺后自动隐藏）
        self._btn_start_all_empty = ShopTextButton("一键启动")
        self._btn_start_all_empty.clicked.connect(self._on_start_all_clicked)
        top_bar_l.addWidget(self._btn_start_all_empty)

        # 店铺标签栏：每个已添加店铺一个标签，点标签=已打开切过去/未打开打开；选中线式滑动指示
        self.shop_tabs = ShopTabBar()
        self.shop_tabs.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.shop_tabs.customContextMenuRequested.connect(self._shop_mgr._store_context_menu)
        self.shop_tabs.currentChanged.connect(self._shop_mgr._on_shop_tab_changed)
        self.shop_tabs.setStyleSheet("""
            QTabBar { background: transparent; }
            QTabBar::tab {
                background: transparent;
                color: #6b7280;
                padding: 4px 20px;
                border: none;
            }
            QTabBar::tab:hover { color: #1f2937; }
            QTabBar::tab:selected {
                color: #2563eb;
            }
            QTabBar QToolButton { background: transparent; border: none; color: #6b7280; }
        """)
        top_bar_l.addWidget(self.shop_tabs)

        # ＋号前留白6px：使"竖线→＋号图标"的距离(约19px)与"竖线→店铺名文字"(20px)对称
        top_bar_l.addSpacing(6)

        # 加号按钮：点击弹出店铺列表弹窗（带启动状态；底部一键启动/添加店铺）——紧跟店铺标签，向左靠齐
        # （标签与＋号之间的浅灰竖线由 ShopTabBar 自己画在最后一个标签右边界，与标签间竖线同款，保证与指示线贴合）
        self._btn_shop_plus = WinButton('plus', height=21, width=23)
        self._btn_shop_plus.clicked.connect(self._show_shop_list_menu)
        top_bar_l.addWidget(self._btn_shop_plus)

        # 空白区：可拖动移动窗口 / 双击最大化还原
        top_bar_l.addStretch(1)

        # 窗口控制按钮（自绘，Chrome 风格）：最小化 / 最大化 / 关闭（缩小）
        self._btn_win_min = WinButton('min', height=21, width=23)
        self._btn_win_min.clicked.connect(self.showMinimized)
        top_bar_l.addWidget(self._btn_win_min)

        self._btn_win_max = WinButton('max', height=21, width=23)
        self._btn_win_max.clicked.connect(lambda: self.showNormal() if self.isMaximized() else self.showMaximized())
        top_bar_l.addWidget(self._btn_win_max)

        self._btn_win_close = WinButton('close', height=21, width=23)
        self._btn_win_close.clicked.connect(self.close)  # 走 closeEvent（默认最小化到托盘）
        top_bar_l.addWidget(self._btn_win_close)

        # 顶栏拖拽：按住空白处移动窗口，双击最大化/还原（对象必须存住，否则被回收后拖拽失效）
        self._title_drag = _TitleBarDrag(self)
        top_bar.installEventFilter(self._title_drag)

        # 顶栏横贯整个窗口顶部（第一层），左侧功能卡片从顶栏下方开始
        main_layout.addWidget(top_bar)

        right_l.addWidget(content, 1)

        # 底部下载状态栏
        self._update_status_label = QLabel("")
        self._update_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update_status_label.setStyleSheet(
            "QLabel { background: #2196F3; color: white; padding: 6px 12px; "
            "font-size: 13px; border-radius: 0px; }"
        )
        self._update_status_label.hide()
        right_l.addWidget(self._update_status_label)

        # 组装：第一层=顶栏（全宽），第二层=中间层（左侧功能卡片 + 右列页面区）
        middle_l.addWidget(right_col, 1)
        main_layout.addWidget(middle, 1)
    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() == QEvent.Type.WindowStateChange:
            try:
                self._btn_win_max.setMaximized(self.isMaximized())  # 最大化↔还原图标切换
            except Exception:
                pass
            # 窗口状态变化（含任务栏最小化/恢复）：恢复的瞬间 isMinimized() 仍可能是旧值（Qt 缓存滞后），
            # 且 Windows 此刻正在播放"恢复放大动画"，过早重排会掐断动画、造成闪一下。
            # 所以延迟到动画基本播完、窗口尺寸稳定后再去重排（此时判断也不再误判）。
            # （最大化溢出已由全局消息过滤器 _FramelessNccalcFilter 在系统层面处理，这里不再做几何校正）
            QTimer.singleShot(350, self._refresh_pages_after_state_change)
    def showEvent(self, e):
        super().showEvent(e)
        # 显示瞬间记录原生句柄给消息过滤器认主（比旧版"启动200毫秒后补记"更早，
        # 系统标题栏在出生第一帧就被抹掉，不闪现）。句柄此时已存在，只是读取，无老坑。
        # 同时开启系统阴影：标题栏被抹掉后 DWM 阴影需要主动激活一次（主流库同款 1px 玻璃边，
        # 不能用 -1——整窗玻璃会带来启动灰圈老毛病；也不能用 0——阴影不生效）。
        try:
            import ctypes as _cse
            self._frameless_hwnd = int(self.winId())
            class _Margins(_cse.Structure):
                _fields_ = [("l", _cse.c_int), ("r", _cse.c_int), ("t", _cse.c_int), ("b", _cse.c_int)]
            _mg = _Margins(1, 1, 1, 1)
            _cse.windll.dwmapi.DwmExtendFrameIntoClientArea(self._frameless_hwnd, _cse.byref(_mg))
            # 通知系统按新规则重算一次窗口框架（SWP_FRAMECHANGED），让"标题栏不占位"立即生效
            _cse.windll.user32.SetWindowPos(self._frameless_hwnd, 0, 0, 0, 0, 0,
                                            0x0001 | 0x0002 | 0x0010 | 0x0020)  # NOSIZE|NOMOVE|NOACTIVATE|FRAMECHANGED
        except Exception:
            pass
        # 首次显示：把窗口物理摆正到屏幕工作区正中（只做一次，之后用户拖到哪算哪）。
        # 背景：本窗口用 NCCALCSIZE 抹掉系统标题栏，Qt 对窗口原点的换算带上了已隐藏的
        # 标题栏高度/隐形边（实测物理落点比期望左8px、下31px，2026-08-28 日志实证）。
        # 注意必须延后摆正：showEvent 当刻 Qt 还没把自己的缓存几何应用完，立刻摆会被
        # 覆盖回去（2026-08-28 实测）；延后 300ms 等 Qt 应用完再摆才稳。
        if not getattr(self, '_centered_once', False):
            self._centered_once = True

            def _recenter():
                try:
                    import ctypes as _cc
                    class _RC(_cc.Structure):
                        _fields_ = [("l", _cc.c_long), ("t", _cc.c_long), ("r", _cc.c_long), ("b", _cc.c_long)]
                    _hwnd = getattr(self, '_frameless_hwnd', None)
                    if not _hwnd:
                        return
                    _rc = _RC()
                    _cc.windll.user32.GetWindowRect(_hwnd, _cc.byref(_rc))
                    _wa = _RC()
                    _cc.windll.user32.SystemParametersInfoW(0x0030, 0, _cc.byref(_wa), 0)  # SPI_GETWORKAREA：任务栏外的可用区
                    _w = _rc.r - _rc.l
                    _h = _rc.b - _rc.t
                    _x = _wa.l + (_wa.r - _wa.l - _w) // 2
                    _y = _wa.t + (_wa.b - _wa.t - _h) // 2
                    _before = (_rc.l, _rc.t)
                    if _before != (_x, _y):
                        _cc.windll.user32.SetWindowPos(_hwnd, 0, _x, _y, 0, 0,
                                                       0x0001 | 0x0004 | 0x0010)  # NOSIZE|NOZORDER|NOACTIVATE
                except Exception:
                    pass
            QTimer.singleShot(300, _recenter)
    def closeEvent(self, e):
        if not self._quitting:
            e.ignore()
            # 真正隐藏到托盘（不再占用任务栏），避开无边框窗口"最小化→恢复"时网页内核错位/空白的毛病
            self.hide()
            self._tray_icon.showMessage("快应AI", "已最小化到托盘，双击托盘图标可显示窗口", QSystemTrayIcon.MessageIcon.Information, 2000)
            return
        _write_exit_flag()  # 写"正常退出"旗子：值班员看到旗子在就不会误拉起
        _write_life('程序正常退出（closeEvent）')
        # 退出前把还没落盘的缓存补写进硬盘（重启不丢）
        try:
            from ai_service import _flush_cache
            _flush_cache()
        except Exception:
            pass
        self._stop_all()
        super().closeEvent(e)
