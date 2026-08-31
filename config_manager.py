# -*- coding: utf-8 -*-
"""
统一配置管家（ConfigManager）
对齐主流桌面软件的做法，根治"文件、内存、页面三份状态不一致"的老问题：

1. 单一真源：全项目配置只认一份文件（用户数据目录 %APPDATA%/快应AI/config.ini），
   谁都不许自己直接翻文件，读写都走本管家。
2. 内存缓存：启动时读一次进内存，运行中读内存；改配置时"内存+文件"一步同时改。
3. 原子写：先写临时文件再替换，防止写到一半断电/崩溃把配置写坏。
4. 默认值真落盘：空配置补默认值时真正写回文件，杜绝"页面有字、文件为空"的假象。
5. 版本迁移：配置文件带版本号，升级时自动补新键、保留旧值。
6. 变更广播：配置改动后通知订阅者（各店铺AI等）刷新内存。
"""
import os
import shutil
import threading
import configparser

APP_NAME = '快应AI'                 # 用户数据目录下的应用名
CONFIG_VERSION = '2'                # 配置文件版本号（用于自动迁移）

# 默认回复策略（迁移/空配置补默认共用这一份）
DEFAULT_TRANSFER_TEXT = "暂无默认策略（开源演示版），请在设置中心自行配置。"

_instance = None
_lock = threading.RLock()


def appdata_config_dir():
    """配置所在目录（用户数据目录），更新/重装软件不会覆盖这里"""
    base = os.environ.get('APPDATA') or os.path.expanduser('~')
    d = os.path.join(base, APP_NAME)
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def appdata_config_path():
    """配置文件真实路径（用户数据目录）"""
    return os.path.join(appdata_config_dir(), 'config.ini')


def legacy_config_path():
    """旧版配置文件路径（程序目录），仅首次启动迁移用"""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')


class ConfigManager:
    def __init__(self):
        self._path = appdata_config_path()
        self._cfg = configparser.ConfigParser()
        self._lock = _lock            # 暴露全局锁（导入配置等外部模块可直接加锁，保证并发安全）
        self._listeners = []          # 变更订阅者
        self._ensure_file()           # 首启动：程序目录旧配置搬到 AppData（不丢数据）
        self._load()                  # 读进内存
        self._migrate()               # 版本迁移：补新键、回退旧键（真落盘）

    # ── 单例 ──
    @classmethod
    def instance(cls):
        global _instance
        if _instance is None:
            with _lock:
                if _instance is None:
                    _instance = cls()
        return _instance

    def _ensure_file(self):
        """首启动：AppData 无配置 → 把程序目录旧 config.ini 原样搬过来"""
        if not os.path.exists(self._path):
            legacy = legacy_config_path()
            if os.path.exists(legacy):
                try:
                    shutil.copy2(legacy, self._path)
                except Exception:
                    pass

    def _load(self):
        if os.path.exists(self._path):
            try:
                self._cfg.read(self._path, encoding='utf-8')
            except Exception:
                self._cfg = configparser.ConfigParser()

    def _migrate(self):
        """版本迁移：补版本号；旧键回退；缺失键补默认并真落盘"""
        changed = False
        if not self._cfg.has_section('meta'):
            self._cfg.add_section('meta')
            changed = True
        if self._cfg.get('meta', 'version', fallback='1') != CONFIG_VERSION:
            self._cfg.set('meta', 'version', CONFIG_VERSION)
            changed = True
        if not self._cfg.has_section('llm'):
            self._cfg.add_section('llm')
            changed = True
        # 旧版单套配置键回退（新键都为空时才回退，不覆盖已有值）
        if (not self._cfg.has_option('llm', 'transfer_pre_sale_scenarios')
                and not self._cfg.has_option('llm', 'transfer_after_sale_scenarios')
                and self._cfg.has_option('llm', 'transfer_scenarios')):
            old = self._cfg.get('llm', 'transfer_scenarios', fallback='') or ''
            self._cfg.set('llm', 'transfer_pre_sale_scenarios', old)
            self._cfg.set('llm', 'transfer_after_sale_scenarios', old)
            changed = True
        # 缺失的配置键 → 补默认并真落盘（杜绝"页面有字、文件为空"的假象）
        for _k in ('transfer_pre_sale_scenarios', 'transfer_after_sale_scenarios'):
            if not self._cfg.has_option('llm', _k):
                self._cfg.set('llm', _k, DEFAULT_TRANSFER_TEXT)
                changed = True
        if changed:
            self.save()

    # ── 读（内存）──
    def get(self, section, key, fallback=''):
        with _lock:
            return self._cfg.get(section, key, fallback=fallback)

    def getint(self, section, key, fallback=0):
        with _lock:
            try:
                return self._cfg.getint(section, key, fallback=fallback)
            except Exception:
                return fallback

    def getfloat(self, section, key, fallback=0.0):
        with _lock:
            try:
                return self._cfg.getfloat(section, key, fallback=fallback)
            except Exception:
                return fallback

    def getboolean(self, section, key, fallback=False):
        with _lock:
            try:
                return self._cfg.getboolean(section, key, fallback=fallback)
            except Exception:
                return fallback

    def has_section(self, section):
        with _lock:
            return self._cfg.has_section(section)

    def has_option(self, section, key):
        with _lock:
            return self._cfg.has_option(section, key)

    # ── 写（内存 + 原子落盘 + 广播一步完成）──
    def set(self, section, key, value, notify=True):
        with _lock:
            self._merge_from_disk()  # 先把其它窗口的最新修改收进来，再改自己的
            if not self._cfg.has_section(section):
                self._cfg.add_section(section)
            self._cfg.set(section, key, str(value).replace('%', '%%'))
            self._atomic_write()
        if notify:
            self._notify(key, str(value))

    def set_many(self, updates, notify=True):
        """updates: [(section, key, value), ...] 批量改，只落盘一次"""
        with _lock:
            self._merge_from_disk()  # 先把其它窗口的最新修改收进来，再改自己的
            for sec, k, v in updates:
                if not self._cfg.has_section(sec):
                    self._cfg.add_section(sec)
                self._cfg.set(sec, k, str(v).replace('%', '%%'))
            self._atomic_write()
        if notify:
            for _, k, v in updates:
                self._notify(k, str(v))

    def save(self):
        with _lock:
            self._atomic_write()

    def reload(self):
        """从文件重新读进内存（导入配置等场景用）"""
        with _lock:
            self._load()

    def raw(self):
        """返回内存中的 ConfigParser（兼容现有代码；只读使用，改完要调 save()）"""
        return self._cfg

    # ── 原子写：先写临时文件再替换，防写坏 ──
    # 临时文件名带进程号：多实例（多开窗口）各自写各自的临时文件，避免互相覆盖写坏配置
    def _atomic_write(self):
        tmp = self._path + '.tmp.' + str(os.getpid())
        with open(tmp, 'w', encoding='utf-8') as f:
            self._cfg.write(f)
        os.replace(tmp, self._path)

    # ── 多实例写保护：写盘前以磁盘为基准刷新内存 ──
    # 程序支持多开，多个窗口共享一份 config.ini。若某窗口内存里是旧值，它一写盘就会把
    # 别人刚改的配置盖回去（黑名单/低优先级被"重启复原"的根因之一）。
    # 解决：每次 set/set_many 修改前，先把磁盘上其它窗口改过的最新值合并进内存，再改再写。
    def _merge_from_disk(self):
        try:
            disk = configparser.ConfigParser()
            disk.read(self._path, encoding='utf-8')
            for sec in disk.sections():
                if not self._cfg.has_section(sec):
                    self._cfg.add_section(sec)
                for k, v in disk.items(sec, raw=True):
                    try:
                        self._cfg.set(sec, k, v)
                    except Exception:
                        pass
        except Exception:
            pass  # 磁盘读不了就保持现状，不阻塞保存

    # ── 变更广播 ──
    def subscribe(self, cb):
        self._listeners.append(cb)

    def _notify(self, key, value):
        for cb in list(self._listeners):
            try:
                cb(key, value)
            except Exception:
                pass
