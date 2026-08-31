# 快应AI - 纯工具模块：路径/余弦/进程探测/诊断写入
# 本模块只依赖标准库与 log_manager，不依赖界面，可独立复用。
import os
import sys
import threading
from datetime import datetime
from log_manager import dated_log_path

# ── 版本号（自动更新比对用，发版时修改；单一来源，main_qt 与主窗口统一引用）──
LOCAL_VERSION = "9.4.5"


def _cosine(a, b):
    """纯Python余弦相似度（不依赖numpy），用于未答问题语义合并"""
    try:
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(y * y for y in b) ** 0.5
        if not na or not nb:
            return 0.0
        return dot / (na * nb)
    except Exception:
        return 0.0


# ── 多开隔离（治本：登录页/设置中心的网页内核数据目录若被两个实例共用，会互相争锁
#    ——轻则事件循环停摆界面卡死数分钟，重则访问冲突崩溃，2026-08-28 排查结论）──
# 每个实例用自己的进程号给这两份内核数据目录命名，各用各的互不干扰；
# 店铺页面的登录态目录仍为共享（多开时同店不重复登录的既有行为不变）。
_si_pid_alive_cache = {}

def _si_pid_is_python(pid):
    """检查进程号是否还活着且属于 python 程序（带缓存，供残留目录清理用）"""
    if pid in _si_pid_alive_cache:
        return _si_pid_alive_cache[pid]
    alive = False
    try:
        import ctypes as _ct
        _h = _ct.windll.kernel32.OpenProcess(0x1000, False, pid)
        if _h:
            _buf = _ct.create_unicode_buffer(520)
            _sz = _ct.c_ulong(520)
            _ok = _ct.windll.kernel32.QueryFullProcessImageNameW(_h, 0, _buf, _ct.byref(_sz))
            _ct.windll.kernel32.CloseHandle(_h)
            if _ok:
                _name = _buf.value.rsplit('\\', 1)[-1].lower()
                alive = _name in ('python.exe', 'pythonw.exe')
    except Exception:
        alive = True  # 探测失败按活着算（宁可不删，不误删）
    _si_pid_alive_cache[pid] = alive
    return alive


def _data_dir():
    """用户数据目录（与数据库模块统一）：数据库/聊天/图片缓存/消息中心等全走这里"""
    try:
        import database
        return database.user_data_dir()
    except Exception:
        return os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), 'data')


def _log_dir():
    """诊断日志目录（不属于用户数据，单独放程序目录下 data/，与数据库模块统一）"""
    try:
        import database
        return database.log_dir()
    except Exception:
        return os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), 'data')


def _pic_dir():
    """用户上传的回复图片目录（用户数据目录下）"""
    d = os.path.join(_data_dir(), 'Picture')
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def _resolve_pic_file(p):
    """把规则里记录的图片路径解析成真实存在的本地文件（路径不存在时按文件名去 Picture 目录兜底找，与发图逻辑一致）"""
    p = (p or '').strip()
    if not p:
        return None
    if os.path.exists(p):
        return p
    b = os.path.basename(p)
    if not b:
        return None
    for cand in (os.path.join(_pic_dir(), b),
                 os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), 'Picture', b)):
        if os.path.exists(cand):
            return cand
    return None


def _remap_pic_path(p, restored_names):
    """导入时：把规则里记录的图片路径改写到新电脑 Picture 目录下对应的文件（按文件名匹配；没恢复过的不动）"""
    p = (p or '').strip()
    if not p:
        return p
    b = os.path.basename(p)
    if b and b in restored_names:
        return os.path.join(_pic_dir(), b)
    return p


def _remap_gk_image_paths(text, restored_names):
    """导入时：把文本里图片类型的路径改写到新电脑 Picture 目录（按文件名匹配；不破坏其它行）"""
    if not text:
        return text
    out = []
    for ln in (text or '').split('\n'):
        s = ln.strip()
        if not s or '|' not in s:
            out.append(ln)
            continue
        parts = s.split('|')
        # 识别行末的 direct/type 尾巴（text/image/transfer）
        if len(parts) >= 4 and parts[-2].strip() in ('0', '1') and parts[-1].strip() in ('text', 'image', 'transfer'):
            tt = parts[-1].strip()
            if tt == 'image':
                r = '|'.join(parts[1:-2]).strip()
                nr = _remap_pic_path(r, restored_names)
                if nr != r:
                    out.append(parts[0] + '|' + nr + '|' + parts[-2].strip() + '|' + tt)
                    continue
        out.append(ln)
    return '\n'.join(out)


# ── 诊断工具数据文件（供独立诊断工具读取，按天命名保留48小时）──
_diag_file_lock = threading.Lock()

def _write_diag_file(msg: str):
    """写入当天的诊断工具数据文件（线程安全）。不做行数裁剪：多个程序实例并发写同一文件时，
    裁剪用的"整读重写"会互相覆盖、丢内容，导致排查时日志时序错乱（2026-08-28 实测踩坑）。
    代价是日志文件会持续变大，属排查期可接受范围（48小时后自动删除）。"""
    try:
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        path = dated_log_path('diag')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with _diag_file_lock:
            with open(path, 'a', encoding='utf-8') as f:
                f.write(f"[{ts}] {msg}\n")
    except:
        pass


def _native_window_rect(w):
    """问操作系统要窗口"看得见的内容区域"（客户区）在屏幕上的位置和大小（物理像素换算回逻辑坐标），
    返回 (x, y, 宽, 高)。比 Qt 记账的 frameGeometry 和整窗矩形都准：整窗矩形外圈带一圈看不见的
    预留边（拖拽缩放/阴影用），照它对齐弹窗会大出一圈。用于登录框/设置中心等需要完全覆盖
    主窗口的弹窗对齐。问不到返回 None，调用方退回 frameGeometry。"""
    try:
        import ctypes
        import ctypes.wintypes as _wt
        _r = _wt.RECT()
        if not ctypes.windll.user32.GetClientRect(int(w.winId()), ctypes.byref(_r)) or _r.right <= _r.left:
            return None
        _pt = _wt.POINT(0, 0)
        ctypes.windll.user32.ClientToScreen(int(w.winId()), ctypes.byref(_pt))
        _dpr = w.devicePixelRatioF() or 1.0
        return (round(_pt.x / _dpr), round(_pt.y / _dpr),
                round((_r.right - _r.left) / _dpr), round((_r.bottom - _r.top) / _dpr))
    except Exception:
        pass
    return None


def _apply_win11_rounded(w):
    """给无边框弹窗应用 Win11 系统圆角（与主程序普通窗口的圆角同款同半径）。
    Win11 会自动给带系统边框的窗口加圆角，无边框窗口不会，需要手动设置；
    Win10 没有此接口（版本号<22000）直接跳过，保持直角不受影响。"""
    try:
        if sys.getwindowsversion().build < 22000:
            return
        import ctypes
        _pref = ctypes.c_int(2)  # 2 = DWMWCP_ROUND（系统标准圆角）
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            int(w.winId()), 33, ctypes.byref(_pref), ctypes.sizeof(_pref))  # 33 = DWMWA_WINDOW_CORNER_PREFERENCE
    except Exception:
        pass


# ── 心跳留痕文件：程序启动/退出/运行心跳都写这里，崩溃或被杀时没有"程序正常退出"记录（按天命名保留48小时）──
_life_lock = threading.Lock()

def _write_life(msg: str):
    """写入当天的心跳留痕（线程安全），超过5000行只保留尾部。
    每行带进程号：值班员凭"某进程号的心跳静默时长"判断该实例是否卡死（自动清理僵尸进程用）"""
    try:
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        path = dated_log_path('life')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with _life_lock:
            with open(path, 'a', encoding='utf-8') as f:
                f.write(f"[{ts}] [pid={os.getpid()}] {msg}\n")
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            if len(lines) > 5000:
                with open(path, 'w', encoding='utf-8') as f:
                    f.writelines(lines[-5000:])
    except:
        pass


# ── "正常退出"旗子：正常退出时写 exit_ok_<pid>.flag，值班员看到旗子在就不会误拉起 ──
#   按实例PID命名，多开实例互不干扰；崩溃/被杀时 closeEvent 不会执行，旗子不在
_exit_flag_dir = _data_dir()

def _write_exit_flag():
    """正常退出时写旗子（带本实例PID，多开实例互不干扰）"""
    try:
        os.makedirs(_exit_flag_dir, exist_ok=True)
        with open(os.path.join(_exit_flag_dir, f'exit_ok_{os.getpid()}.flag'), 'w', encoding='utf-8') as f:
            f.write(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    except Exception:
        pass