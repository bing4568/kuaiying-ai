# -*- coding: utf-8 -*-
"""Qt6 + QtWebEngine 内嵌浏览器兼容层。

业务代码统一以 `from qt_web_compat import QtView as QWebEngineView, ...` 别名导入，
本模块导出 Qt6 的 QtWebEngine 真实类（更名 Qt*），并补齐业务代码用到、
但 Qt6 已改名移位的接口（见各注释）。

采用 Qt 内置浏览器（QtWebEngine）：
  - 窗口嵌入：QtWebEngine 是 Qt 原生控件，天然能嵌进 Qt 布局并跟随窗口，
    无需跨线程宿主窗体 hack。
  - 枚举常量：Qt6 把 ForcePersistentCookies / DiskHttpCache / DocumentCreation /
    MainWorld / NavigationTypeLinkClicked 等移进了枚举命名空间，
    这里在子类上补回顶层别名，业务代码可继续按旧写法引用。
  - 本地目录映射用自定义协议 kuaai://（官方正规做法，不走"转跳"，
    绕开 Chrome 禁止 https→file 转跳的安全规则）、远程调试端口
    用 QTWEBENGINE_REMOTE_DEBUGGING 环境变量。
"""
import os

from PyQt6.QtCore import QFile, QIODevice
from PyQt6.QtWebEngineCore import (
    QWebEngineProfile as _Profile,
    QWebEnginePage as _Page,
    QWebEngineScript as _Script,
    QWebEngineUrlRequestInterceptor,
    QWebEngineUrlRequestInfo,
    QWebEngineUrlRequestJob,
    QWebEngineUrlScheme,
    QWebEngineUrlSchemeHandler,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView as _View

# ── 注册内部协议 kuaai://：把登记过的本地目录当网站直接端给浏览器 ──
# 必须在内核首次使用前注册，放模块顶部（import 时）即最早期，安全。
_scheme = QWebEngineUrlScheme(b'kuaai')
_scheme.setFlags(QWebEngineUrlScheme.Flag.SecureScheme
                 | QWebEngineUrlScheme.Flag.LocalScheme
                 | QWebEngineUrlScheme.Flag.LocalAccessAllowed
                 | QWebEngineUrlScheme.Flag.CorsEnabled)
QWebEngineUrlScheme.registerScheme(_scheme)

# {host: 本地目录}：mapVirtualHost 登记，kuaai:// 请求按这里找到真实文件
_HOST_FOLDERS = {}


class _HostSchemeHandler(QWebEngineUrlSchemeHandler):
    """kuaai://<host>/<路径> → 直接返回登记目录里的本地文件。
    不做任何"转跳"（Chrome 禁止 https→file 转跳，就是 ERR_UNSAFE_REDIRECT 的来源）。"""

    def requestStarted(self, job):
        try:
            url = job.requestUrl()
            folder = _HOST_FOLDERS.get(url.host())
            full = self._resolve(folder, url.path().lstrip('/'))
            if not full:
                job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
                return
            import mimetypes
            mime = (mimetypes.guess_type(full)[0] or 'application/octet-stream').encode()
            if mime.startswith(b'text/'):
                mime += b'; charset=utf-8'
            f = QFile(full)
            if not f.open(QIODevice.OpenModeFlag.ReadOnly):
                job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
                return
            f.setParent(job)  # 跟请求同生共死，防文件对象被提前回收
            job.reply(mime, f)
        except Exception:
            try:
                job.fail(QWebEngineUrlRequestJob.Error.Failed)
            except Exception:
                pass

    @staticmethod
    def _resolve(folder, rel):
        """目录内相对路径 → 真实文件全路径；越出目录或文件不存在返回 None。"""
        if not folder:
            return None
        from urllib.parse import unquote
        base = os.path.normpath(folder).lower() + os.sep
        for cand in dict.fromkeys((rel, unquote(rel))):  # 去重，两种编码形式各试一次
            full = os.path.normpath(os.path.join(folder, cand))
            if full.lower().startswith(base) and os.path.isfile(full):
                return full
        return None


DEFAULT_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "Chrome/120.0.0.0 Safari/537.36")

_BROWSER_ARGS = '--disable-background-timer-throttling --autoplay-policy=no-user-gesture-required'

# 允许的内部协议白名单（与旧桥接一致，kuaai 是本地目录映射用的内部协议）
_SAFE_SCHEMES = {'http', 'https', 'file', 'about', 'data', 'blob', 'kuaai', ''}


def warmup(profile_name='warmup'):
    """启动预热占位。QtWebEngine 由 Qt 统一管理、随用随建；主线程外创建会崩溃，
    故这里返回成功但不做任何事（旧代码在后台线程调用，必须无副作用）。"""
    return True


class QtScript(_Script):
    """QWebEngineScript 子类：补回 Qt6 已移入枚举命名空间的注入点/世界常量。"""
    DocumentCreation = _Script.InjectionPoint.DocumentCreation
    MainWorld = _Script.ScriptWorldId.MainWorld


class _PageInterceptor(QWebEngineUrlRequestInterceptor):
    """页面级 URL 拦截器：只承担导航拦截（调用页面挂载的 acceptNavigationRequest 判定函数，
    拦掉非内置协议）。本地目录映射已改由 kuaai:// 协议服务员负责，不再在这里转跳。
    通过 setUrlRequestInterceptor 挂到页面所属的 profile 上（登录/设置页各自独立 profile）。"""

    def __init__(self, page, parent=None):
        super().__init__(parent)
        self._page = page

    def _apply_nav(self, info):
        try:
            fn = getattr(self._page, '_accept_fn', None)
            if fn is None:
                return
            url = info.requestUrl()
            scheme = url.scheme().lower()
            if scheme not in _SAFE_SCHEMES:
                info.block(True)
        except Exception:
            pass

    def interceptRequest(self, info):
        # 导航拦截：仅主框架导航才做协议白名单判定（子资源不拦截，避免误伤图片等）
        try:
            rtype = info.resourceType()
            if rtype == QWebEngineUrlRequestInfo.ResourceType.ResourceTypeMainFrame:
                self._apply_nav(info)
        except Exception:
            pass


class QtProfile(_Profile):
    """QWebEngineProfile 子类：补回顶层枚举别名 + 收集远程调试端口。"""
    ForcePersistentCookies = _Profile.PersistentCookiesPolicy.ForcePersistentCookies
    DiskHttpCache = _Profile.HttpCacheType.DiskHttpCache

    def __init__(self, name, parent=None):
        super().__init__(name, parent)
        self._ua = DEFAULT_UA
        self._extra_args = ''

    def setHttpUserAgent(self, ua):
        self._ua = ua or DEFAULT_UA
        super().setHttpUserAgent(self._ua)

    def setExtraBrowserArguments(self, args):
        """收集远程调试端口（--remote-debugging-port=N）。
        QtWebEngine 需在 Chromium 启动前设 QTWEBENGINE_REMOTE_DEBUGGING 才生效；
        此处记录并尽力设置，实际生效时机后续校验。"""
        self._extra_args = ' '.join(a for a in str(args).split() if a)
        try:
            for a in self._extra_args.split():
                if a.startswith('--remote-debugging-port='):
                    os.environ['QTWEBENGINE_REMOTE_DEBUGGING'] = a.split('=', 1)[1]
                    break
        except Exception:
            pass


class QtPage(_Page):
    """QWebEnginePage 子类：
      - 用属性读写 acceptNavigationRequest（旧桥接语义），实际拦截由 _PageInterceptor 执行；
      - 补回 NavigationTypeLinkClicked 顶层别名；
      - 支持 mapVirtualHost 登记本地目录映射（kuaai:// 协议方式）。"""
    NavigationTypeLinkClicked = _Page.NavigationType.NavigationTypeLinkClicked

    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        self._accept_fn = None          # 由页面按需挂载的导航判定函数
        self._nav_interceptor = None

    @property
    def acceptNavigationRequest(self):
        # 直接返回判定函数本身（若用户未挂载，返回一个恒通过的默认函数）
        if self._accept_fn is None:
            return lambda url, typ, isMain: True
        return self._accept_fn

    @acceptNavigationRequest.setter
    def acceptNavigationRequest(self, fn):
        self._accept_fn = fn

    def _setup_interceptor(self):
        if self._nav_interceptor is None:
            try:
                self._nav_interceptor = _PageInterceptor(self, self)
                self.profile().setUrlRequestInterceptor(self._nav_interceptor)
            except Exception:
                import traceback
                traceback.print_exc()

    def _add_host_map(self, host, folder):
        # 登记 host→目录，并在当前 profile 上挂一次 kuaai:// 本地文件服务员
        _HOST_FOLDERS[str(host)] = str(folder)
        try:
            profile = self.profile()
            if getattr(profile, '_kuaai_handler', None) is None:
                handler = _HostSchemeHandler(profile)  # 挂在 profile 上防回收
                profile.installUrlSchemeHandler(b'kuaai', handler)
                profile._kuaai_handler = handler
        except Exception:
            import traceback
            traceback.print_exc()


class QtView(_View):
    """QWebEngineView 子类：
      - 兼容旧代码 `web.setHtml(...)`（真实 QWebEngineView 无此方法，转交给 page）；
      - `web.mapVirtualHost(...)`：本地目录映射；
      - `web.setDeferResize(...)`：旧侧栏动画用，QtWebEngine 原生跟随容器，保留为无操作。"""

    def setDeferResize(self, defer):
        # QtWebEngine 是原生控件，跟随父容器自动调整，无需攒着等 150ms
        pass

    def mapVirtualHost(self, host, folder):
        try:
            page = self.page()
            if page is not None and hasattr(page, '_add_host_map'):
                page._add_host_map(host, folder)
        except Exception:
            import traceback
            traceback.print_exc()

    def setHtml(self, html, base_url=None):
        page = self.page()
        if page is not None:
            if base_url is not None:
                page.setHtml(html, base_url)
            else:
                page.setHtml(html)