# 快应AI - PyQt6 + QtWebEngine 内核
import sys, os, json, re, time, traceback, hashlib, subprocess, tempfile, shutil, zipfile, threading


# ── 版本号（自动更新比对用，发版时修改）──
LOCAL_VERSION = "9.4.5"

# ══════════════════════════════════════════════════════════
#  调试模式：加 --debug 参数启动时启用调试输出
#  用法：KuaiYingAI.exe --debug
# ══════════════════════════════════════════════════════════
_DEBUG_MODE = '--debug' in sys.argv

# ── 值班员模式：主程序崩溃/被杀后由值班员自动拉起。此进程只加载基本库，不碰界面 ──
#   主程序正常启动时会用 --watchdog <主程序PID> 拉起本进程；值班员检测到主程序
#   非正常消失后，自动带 --restored 参数把主程序重新拉起来（并恢复上次状态）。
if '--watchdog' in sys.argv:
    try:
        from watchdog import run_watchdog
        sys.exit(run_watchdog())
    except Exception:
        sys.exit(0)

# ── 多开隔离（治本：登录页/设置中心的网页内核数据目录若被两个实例共用，会互相争锁
#    ——轻则事件循环停摆界面卡死数分钟，重则访问冲突崩溃，2026-08-28 排查结论）──
# 每个实例用自己的进程号给这两份内核数据目录命名，各用各的互不干扰；
# 店铺页面的登录态目录仍为共享（多开时同店不重复登录的既有行为不变）。


# ── 崩溃留痕：默认启用 faulthandler，程序崩溃时把Python调用栈写进 kuaiai_crash.log ──
#   kuaiai_crash.log 保留现场：每次启动先把上一份改名 kuaiai_crash.prev.log 备份
_LOG_FILE = None
if _DEBUG_MODE:
    _crash_dirs = [tempfile.gettempdir(), os.path.dirname(sys.executable)]
else:
    # 兜底解析：手动启动时启动命令可能写的是相对路径（如"python -u main_qt.py"），
    # dirname会得到空串导致整个崩溃留痕被跳过（2026-08-28 实测：手动启动的实例崩溃无任何记录）。
    # 故统一换成绝对路径解析，脚本目录解析失败再退到当前工作目录。
    _self_dir = os.path.dirname(os.path.abspath(__file__))
    _argv_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    _crash_dirs = [_argv_dir, _self_dir, os.getcwd()]
for _dir in _crash_dirs:
    try:
        if not os.path.isdir(_dir): continue
        _lp = os.path.join(_dir, 'kuaiai_crash.log')
        _lp_prev = os.path.join(_dir, 'kuaiai_crash.prev.log')
        if os.path.exists(_lp):
            try: os.replace(_lp, _lp_prev)
            except Exception:
                # 轮转失败（旧文件多半被卡死的进程占着句柄）：换带时间戳的新文件写。
                # 绝不能原地清空——旧文件里可能有上次卡死的自动取证内容（2026-08-28 踩坑）
                _lp = os.path.join(_dir, 'kuaiai_crash_%s.log' % time.strftime('%Y%m%d_%H%M%S'))
        _LOG_FILE = open(_lp, 'w', encoding='utf-8', buffering=1)
        _LOG_FILE.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {'DEBUG' if _DEBUG_MODE else 'NORMAL'} START\n")
        _LOG_FILE.write(f"Python: {sys.version}\nEXE: {sys.executable}\n")
        _LOG_FILE.flush()
        break
    except Exception:
        _LOG_FILE = None
import faulthandler
if _LOG_FILE:
    faulthandler.enable(file=_LOG_FILE)
elif sys.stderr is not None:
    faulthandler.enable()
if _DEBUG_MODE and _LOG_FILE:
    sys.stdout = _LOG_FILE
    sys.stderr = _LOG_FILE

def _global_excepthook(type, value, tb):
    traceback.print_exception(type, value, tb)
    try:
        sys.stderr.flush()
    except Exception:
        pass
sys.excepthook = _global_excepthook

# ══════════════════════════════════════════════════════════
#  PyInstaller 打包修复
# ══════════════════════════════════════════════════════════
if getattr(sys, 'frozen', False):
    _cacert = os.path.join(sys._MEIPASS, 'certifi', 'cacert.pem')
    if os.path.exists(_cacert):
        os.environ['SSL_CERT_FILE'] = _cacert


from datetime import datetime
import time
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
# 店铺标签页内核：统一使用 Qt 内置浏览器（QtWebEngine）
from qt_web_compat import (
    QtView as QWebEngineView,
    QtProfile as QWebEngineProfile,
    QtPage as QWebEnginePage,
    QtScript as QWebEngineScript,
)

from fire_browser.pathutils import (
    _si_pid_is_python, _data_dir, _write_life,
)
from fire_browser.browser_tab import BrowserTab
from fire_browser.main_window import FireBrowser
from fire_browser.main_window._frameless import _FramelessNccalcFilter
from fire_browser.settings_bridge import warm_settings_network


sys.path.insert(0, os.path.dirname(__file__))
try:
    import database
    from message_modules import ReplyEngine, MessageSender
    HAS_DB = True
except:
    HAS_DB = False

from message_scheduler import Scheduler

try:
    from ai_service import AIService
except Exception as e:
    print(f"[AIService] 导入失败: {e}", flush=True)
    AIService = None


# ============ 启动 ============
if __name__ == '__main__':
    # 日志按天命名默认保留48小时：启动时删掉前天及更早的旧日志（运行/诊断/心跳/调试，含旧版固定名文件）
    try:
        import log_manager as _log_mgr
        _log_mgr.cleanup_old_logs()
    except Exception:
        pass
    # 崩溃日志（程序目录/临时目录）：修改时间超过48小时的 kuaiai_crash*.log 一并清理
    try:
        _crash_cutoff = datetime.now().timestamp() - 2 * 86400
        for _d in set(_crash_dirs):
            try:
                for _n in os.listdir(_d):
                    if _n.startswith('kuaiai_crash') and _n.endswith('.log'):
                        _p = os.path.join(_d, _n)
                        try:
                            if os.path.getmtime(_p) < _crash_cutoff:
                                os.remove(_p)
                        except Exception:
                            pass
            except Exception:
                pass
    except Exception:
        pass
    if _DEBUG_MODE:
        print("[DIAG] main_qt.py entry", flush=True)
    # 关闭控制台快速编辑模式，防止误点CMD窗口导致程序暂停
    if sys.platform == 'win32':
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-10)  # STD_INPUT_HANDLE
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            ENABLE_QUICK_EDIT = 0x0040
            ENABLE_EXTENDED_FLAGS = 0x0080
            kernel32.SetConsoleMode(handle, (mode.value & ~ENABLE_QUICK_EDIT) | ENABLE_EXTENDED_FLAGS)
        if not _DEBUG_MODE:
            ctypes.windll.user32.ShowWindow(kernel32.GetConsoleWindow(), 0)
    if _DEBUG_MODE:
        print("[DIAG] Creating QApplication", flush=True)
    # 进程设为逐显示器缩放感知（Per-Monitor V2），
    # 并让 Qt 按物理像素布局，避免窗口/网页控件缩放基准不一致导致错位或超出屏幕
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass
    # 150% 等缩放：让 Qt 用精确的 1.25/1.5 倍缩放，而不是四舍五入成 1/2 倍，
    # 与内嵌 Chromium 的缩放保持一致，解决"一打开就操作区域/全屏错位"（需 Qt>=5.14）
    try:
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_SetHighDpiScaleFactorRoundingPolicy,
                                  Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    except Exception:
        pass
    # 无边框窗口里内嵌原生控件（如 QWebEngineView）时，Windows 下"最小化→恢复"容易让
    # 原生子窗口读到旧区域而错位/空白。开启此项让 Qt 尽量复用同一个原生窗口，减轻偏移。
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_DontCreateNativeWidgetSiblings, True)
    app = QApplication(sys.argv)
    app.setOrganizationName("KuaiYingAI")
    app.setApplicationName("KuaiYingAI")
    if _DEBUG_MODE:
        print("[DIAG] QApplication created OK", flush=True)
    app.setStyle('Fusion')
    app.setFont(QFont("Microsoft YaHei", 9))
    # ── QtWebEngine 预构建（PyQt6 适配核心）：本机实测"主窗口可见后"再创建
    #    Profile/Page 必崩（PyQt6=访问冲突 / PySide6=永久挂起），而"事件循环启动前"
    #    创建则一切正常（已做大量对照实验确认此规律）。
    #    故在 exec 之前把登录页要用的 Profile/Page 预先造好并保活，
    #    登录对话框打开时只做 view.setPage 装配。 ──
    _WEBENGINE_WARMUP_REFS = None
    _PREBUILT_LOGIN_PAGE = None
    _PREBUILT_RSC_PAGE = None
    try:
        from PyQt6.QtWebEngineCore import QWebEngineProfile as _WarmProf, QWebEnginePage as _WarmPage
        _warm_prof = _WarmProf('qt6_warmup', None)
        _warm_page = _WarmPage(_warm_prof, None)
        _WEBENGINE_WARMUP_REFS = (_warm_prof, _warm_page)
        # 多开隔离：登录页/设置中心的数据目录按本实例进程号命名，避免与其它实例争锁
        _inst_suffix = '_p%d' % os.getpid()
        _login_prof = _WarmProf('login_dialog' + _inst_suffix, None)
        _login_page = _WarmPage(_login_prof, None)
        _PREBUILT_LOGIN_PAGE = (_login_prof, _login_page)
        # 店铺登录页专用：同样预建内核（exec 前建好）。否则打开店铺页时"窗口显示后再建内核"
        # 会崩，导致店铺页打不开、顶部标签与运行状态不显示。注入给 browser_tab 复用。
        _shop_prof = _WarmProf('shop_login' + _inst_suffix, None)
        try:
            import fire_browser.browser_tab.browser_tab as _btm
            _btm.PREBUILT_SHOP_PROFILE = _shop_prof
        except Exception:
            pass
        # 设置中心专用：同样预建内核配置+页面（此前每次打开都现场新建，
        # 正撞"主窗口可见后创建必崩"的雷区——间歇性访问冲突/闪退，2026-08-28 定位）
        _rsc_prof = QWebEngineProfile('settings_center' + _inst_suffix, None)
        _rsc_page = QWebEnginePage(_rsc_prof, None)
        _PREBUILT_RSC_PAGE = (_rsc_prof, _rsc_page)
        # 清理历史残留：已退出实例遗留的"按进程号隔离"数据目录（进程不在了就直接删）
        try:
            import re as _re
            _qe_base = os.path.join(QStandardPaths.writableLocation(QStandardPaths.StandardPath.AppDataLocation),
                                    'QtWebEngine')
            if os.path.isdir(_qe_base):
                for _d in os.listdir(_qe_base):
                    _m = _re.match(r'^(login_dialog|settings_center)_p(\d+)$', _d)
                    if _m and not _si_pid_is_python(int(_m.group(2))):
                        import shutil as _sh
                        _sh.rmtree(os.path.join(_qe_base, _d), ignore_errors=True)
        except Exception:
            pass
    except Exception:
        traceback.print_exc()
    # ── 全局提示框样式：白底黑字圆角卡片，避免默认黑底 ──
    app.setStyleSheet("""
        QToolTip, QToolTip#qt-tooltip, QTipLabel {
            background: #ffffff;
            color: #1f2937;
            border: 1px solid #e0e4ed;
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 12px;
        }
    """)
    # ── 兜底：直接改提示框调色板（白底黑字），不依赖样式表选择器匹配 ──
    _tip_pal = QToolTip.palette()
    _tip_pal.setColor(QPalette.ColorRole.ToolTipBase, QColor('#ffffff'))
    _tip_pal.setColor(QPalette.ColorRole.ToolTipText, QColor('#1f2937'))
    QToolTip.setPalette(_tip_pal)

    # ── 全局移除无边框页面的 DWM 毛玻璃边框 + 兜底摘掉标题栏问号按钮 ──
    # 只对无边框的内置页面（设置中心等全屏页面）生效；
    # 普通弹窗和文件选择框不处理——改窗口样式会先隐藏再显示，打断文件框的模态等待，导致它闪一下就关闭
    import ctypes as _ctypes
    class _DialogBorderRemover(QObject):
        def eventFilter(self, obj, event):
            if event.type() == QEvent.Type.Show and isinstance(obj, QDialog) and (obj.windowFlags() & Qt.WindowType.FramelessWindowHint):
                # 兜底：无边框页面只要还带着问号按钮标志就摘掉（延迟执行，避免事件重入）
                if obj.windowFlags() & Qt.WindowType.WindowContextHelpButtonHint:
                    QTimer.singleShot(0, lambda w=obj: (
                        w.setWindowFlags(w.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint), w.show()))
                try:
                    hwnd = int(obj.winId())
                    margins = (_ctypes.c_int * 4)(-1, -1, -1, -1)
                    _ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(hwnd, _ctypes.byref(margins))
                except:
                    pass
            return False
    app.installEventFilter(_DialogBorderRemover(app))

    # ── 滚动条样式常量（代替 app.setStyleSheet，避免干扰 QWebEngineView） ──
    # 用法: d.setStyleSheet(dialog_style + SCROLLBAR_STYLE)

    window = FireBrowser()
    # 后台预热设置中心数据，打开设置中心不再现场联网卡主线程
    threading.Thread(target=warm_settings_network, daemon=True).start()
    # ── 主窗口的系统消息处理（须装在"事件分发器"上，实测装 app 对象上拦不到消息）──
    # 只处理 WM_NCCALCSIZE：让系统标题栏不占位（主窗口是天生普通窗口，阴影/贴边拉伸
    # 由系统原生负责，无需任何干预）。窗口句柄在首次显示的 showEvent 里记录，此前空转。
    # ⚠️ 过滤器消息分支体内只准 ctypes 调系统接口，不准调 Qt —— 消息中途重入 Qt 会闪退。
    # 【拆解实验开关】设环境变量 KUAI_NO_NCC=1 可跳过本过滤器（定位卡死触发点用）：
    # 跳过时窗口会显示系统标题栏，仅外观变化，功能不受影响。
    if os.environ.get('KUAI_NO_NCC') == '1':
        window._log_to_window("[实验] 已跳过全局消息过滤器（KUAI_NO_NCC=1），窗口显示系统标题栏")
    else:
        _ncc_filter = _FramelessNccalcFilter(lambda: getattr(window, '_frameless_hwnd', None))
        try:
            QAbstractEventDispatcher.instance().installNativeEventFilter(_ncc_filter)
        except Exception:
            app.installNativeEventFilter(_ncc_filter)  # 兜底：分发器不可用时退回 app 级
    # 只在「崩溃自动重启」（值班员带 --restored 拉起）时才提示；手动启动一律不提示。
    # 是否真崩溃已由值班员按"正常退出旗子"判定，--restored 参数就是最可靠的崩溃恢复信号
    if '--restored' in sys.argv:
        # 值班员确认上次为异常退出 → 崩溃恢复启动，提示用户（不弹窗打扰，写日志+状态栏）
        try:
            window._log_to_window("检测到上次程序异常结束（非正常退出），可能发生过崩溃，可查看 kuaiai_crash.log")
        except Exception:
            pass
    _write_life('程序启动')  # 心跳留痕：记录本次启动
    window._log_to_window(f"快应AI v{LOCAL_VERSION} 已启动")
    # ── 内核预热（提前握手）：后台线程提前创建环境，之后打开店铺不再等内核初始化 ──
    def _qt_web_warmup():
        try:
            import qt_web_compat as _qt_compat
            _qt_compat.warmup()
        except Exception:
            pass
    threading.Thread(target=_qt_web_warmup, daemon=True).start()
    # 主窗口为天生普通窗口：系统阴影/贴边拉伸由系统原生提供，无需任何初始化代码
    # （旧的 _apply_frame_shadow"无边框+事后补样式"方案已于 2026-08-28 删除，详见 FireBrowser.__init__ 注释）
    window.showNormal()
    # 显示主界面的同时执行启动检查（开源版直接进入主界面）
    try:
        window._check_login()
    except Exception:
        pass
    # ── 测试模式（测试.bat 拉起）：弹出模块开关面板，所有功能默认关闭，逐个勾选定位卡死元凶 ──
    if getattr(window, '_test_mode', False):
        window._create_test_panel()
        window._log_to_window("[测试模式] 本次为测试启动：所有功能模块默认关闭，请在'测试开关'面板逐个勾选")
    # ── 拉起值班员（独立进程）：主程序崩溃/被杀后由它自动拉起本程序 ──
    # 只有安装版（打包后的 exe）才自动重启；源码运行崩溃就直接退出，方便直接看报错
    try:
        if getattr(sys, 'frozen', False):
            import watchdog as _wd
            _wd.spawn_watchdog(os.getpid())
    except Exception:
        pass
    # ── 恢复模式（值班员拉起时带的参数）：自动打开店铺 + 恢复监控开关 ──
    if '--restored' in sys.argv:
        try:
            window._log_to_window("检测到本次为崩溃恢复启动，正在自动打开店铺并恢复上次状态...")
            # 读取上次监控开关状态（没记录则默认开）
            _last_monitor = True
            try:
                _sp2 = os.path.join(_data_dir(), 'monitor_state.json')
                if os.path.exists(_sp2):
                    with open(_sp2, 'r', encoding='utf-8') as f:
                        _last_monitor = bool(json.load(f).get('monitor', True))
            except Exception:
                pass
            window._auto_monitor_state = _last_monitor
            # 延迟一点等窗口完全就绪，再启动店铺和监控
            QTimer.singleShot(2000, lambda: window._start_all())
        except Exception:
            pass
    sys.exit(app.exec())
    
