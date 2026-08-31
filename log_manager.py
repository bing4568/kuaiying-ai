# 快应AI - 日志系统
"""所有日志的统一管理：运行日志写独立文件，消息日志写对应 QTextEdit 控件。"""
import os
import queue
import re
import threading
import time
from datetime import datetime, timedelta
from PyQt6.QtCore import QTimer

# 消息日志面板最多保留的行数（与运行日志面板一致，超了自动删最旧，防止越渲染越卡）
MAX_MSG_PANEL_LINES = 500

# ── 日志目录与按天命名的日志文件（默认保留48小时：今天+昨天，前天及更早自动删除）──
def _log_dir():
    """日志目录：程序目录下 data/（与诊断日志同目录，更新重装不丢）"""
    try:
        import database
        d = database.log_dir()
    except Exception:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def dated_log_path(prefix):
    """按天命名的日志文件路径（如 run_20260828.log）：跨天自动换新文件，旧文件由 cleanup_old_logs 统一清理"""
    return os.path.join(_log_dir(), '%s_%s.log' % (prefix, datetime.now().strftime('%Y%m%d')))


# 日志保留天数：2天 ≈ 48小时
LOG_KEEP_DAYS = 2

# 旧版固定名日志（本次改造前就在用的），按"修改时间超48小时"兜底清理
_LEGACY_LOG_NAMES = ('run.log', 'diag.log', 'life.log', 'bug_debug.log')


def cleanup_old_logs():
    """删除过期日志：按天命名的文件删"前天及更早"的；旧版固定名文件按修改时间超48小时删。
    启动时调用一次，之后由写入函数在跨天时自动再触发，长期挂机也不会积攒旧日志。"""
    try:
        d = _log_dir()
        cutoff = (datetime.now() - timedelta(days=LOG_KEEP_DAYS)).date()
        mtime_cutoff = datetime.now().timestamp() - LOG_KEEP_DAYS * 86400
        for name in os.listdir(d):
            m = re.search(r'_(\d{8})\.log$', name)
            if m:
                # 按天命名的：文件名里的日期在前天及更早 → 删
                try:
                    if datetime.strptime(m.group(1), '%Y%m%d').date() < cutoff:
                        os.remove(os.path.join(d, name))
                except Exception:
                    pass
            elif name in _LEGACY_LOG_NAMES:
                # 旧版固定名的：超过48小时没再写入 → 删
                try:
                    p = os.path.join(d, name)
                    if os.path.getmtime(p) < mtime_cutoff:
                        os.remove(p)
                except Exception:
                    pass
    except Exception:
        pass


_last_cleanup_day = [None]


def _maybe_daily_cleanup():
    """跨天时自动清理一次过期日志（每次写日志时顺带检查，开销只是一次日期比较）"""
    today = datetime.now().date()
    if _last_cleanup_day[0] != today:
        _last_cleanup_day[0] = today
        cleanup_old_logs()


_run_log_lock = threading.Lock()
_run_log_line_count = 0


def _write_run_log(msg: str, max_lines=5000):
    """写入当天的运行日志文件（线程安全）。超过 max_lines 行自动只保留尾部，防止无限增长。"""
    global _run_log_line_count
    try:
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with _run_log_lock:
            _maybe_daily_cleanup()
            path = dated_log_path('run')
            with open(path, 'a', encoding='utf-8') as f:
                f.write(f"[{ts}] {msg}\n")
            _run_log_line_count += 1
            if _run_log_line_count % 200 == 0:
                _trim_run_log(path, max_lines)
    except Exception:
        pass


def _trim_run_log(path, max_lines):
    """超过 max_lines 时只保留最后 max_lines 行（防止日志文件无限膨胀）"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        if len(lines) <= max_lines:
            return
        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(lines[-max_lines:])
    except Exception:
        pass

# 开源演示版：原日志过滤已移除，此掩码置空（不再过滤任何日志行）
_LOG_FILTER = re.compile(r'^$')

# 滚动条样式（浅灰底、圆角滑块、悬停变蓝）
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


class LogManager:
    """日志管理器：持有所有日志面板的引用，提供统一的写入方法"""

    def __init__(self, msg_log_text=None, diag_cb=None):
        self.msg_log_text = msg_log_text          # 消息日志控件（"更多功能"弹窗里看）
        self._diag_cb = diag_cb                   # 诊断日志回调
        self._main_thread = threading.current_thread()  # 创建时的主线程引用（子线程日志入队，主线程统一写文件）
        self._win_log_queue = queue.Queue()       # 子线程日志的安全队列（主线程定时器统一消费写文件）
        self._msg_panel_lines = {}  # 消息日志行缓存
        self._render_pending = {}   # 80ms防抖标记
        self.test_gate = None       # 测试模式回调：返回False时不渲染（主窗口注入，非测试模式不设置）

    # ── 日志写入 ──

    def log_to_window(self, text):
        """写入运行日志文件（text已包含时间戳，部分带颜色标记）。
        线程安全：非主线程一律入队，由主线程定时器统一写文件——
        避免多线程同时写文件时交错串行。"""
        if threading.current_thread() is not self._main_thread:
            self._win_log_queue.put(text)
            return
        self._append_window_log(text)

    def _append_window_log(self, text):
        """真正写运行日志文件（只允许主线程调用）"""
        _write_run_log(text)

    def drain_window_logs(self):
        """主线程定时调用：把子线程积压的日志队列写到文件（线程安全写法的消费端）"""
        while True:
            try:
                text = self._win_log_queue.get_nowait()
            except Exception:
                break
            try:
                self._append_window_log(text)
            except Exception:
                pass

    # ── 开源演示版：消息日志渲染已移除（原 insert_msg_line/_do_render/flush_panel/load_buyer_msgs），
    # 仅保留空实现占位，避免外部调用报错，不含任何业务逻辑。

    def insert_msg_line(self, shop_name, buyer_uid, unix_ts, source, role, content):
        return

    def _do_render(self, shop_name):
        return

    def flush_panel(self, shop_name):
        return

    def load_buyer_msgs(self, shop_name, buyer_uid, msg_cache):
        return
