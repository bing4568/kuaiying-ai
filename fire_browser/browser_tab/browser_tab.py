# 快应UI 开源版 - 店铺工作页
# 本页只提供"店铺登录"能力：点开店铺标签后内置一个网页，加载拼多多商家后台，
# 用户可扫码/登录进入自己的店铺后台。不做任何消息收发、不接管任何平台业务。
from fire_browser.browser_tab._deps import *

# 店铺登录专属网页内核（由 main_qt 在窗口显示前预建并注入，避免"可见后建内核"崩）
PREBUILT_SHOP_PROFILE = None


def _shop_profile():
    if PREBUILT_SHOP_PROFILE is not None:
        return PREBUILT_SHOP_PROFILE
    return QWebEngineProfile('shop_login')


class BrowserTab(QWidget):
    """店铺工作页：仅打开拼多多商家后台供登录，无任何消息处理。"""

    def __init__(self, shop=None, log_callback=None, diag_callback=None):
        super().__init__()
        # 保留店铺数据引用：顶层标签栏判断"该店是否已打开"依赖 tab.shop（主程序同款），
        # 丢了它 _refresh_shops 会认为没有已打开的店铺，顶部标签永远出不来。
        self.shop = shop
        # 尽力取店铺名（shop 可能是 dict 或对象）
        try:
            if isinstance(shop, dict):
                self.shop_name = str(shop.get('shop_name', '') or '')
            else:
                self.shop_name = str(getattr(shop, 'shop_name', '') or '')
        except Exception:
            self.shop_name = ''
        self.shop_name = self.shop_name or '店铺'
        self.monitoring = False
        self.web = None
        self._blacklist = set()
        self._lp_config = {}
        self._transfer_mute = {}
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        web = QWebEngineView(self)
        web.setPage(QWebEnginePage(_shop_profile(), web))
        # 拼多多商家后台：登录后即进入自己的店铺后台（仅登录，不做任何消息处理）
        web.setUrl(QUrl('https://mms.pinduoduo.com/'))
        lay.addWidget(web)
        self.web = web

    def _set_monitoring(self, on):
        """设置运行状态（界面运行中效果用；不触达任何消息处理）"""
        self.monitoring = bool(on)

    def _refresh(self):
        """基础界面刷新钩子（保留，便于主程序统一调用）"""
        try:
            if self.web is not None:
                self.web.update()
        except Exception:
            pass

    def __getattr__(self, name):
        # 其它遗留的未定义接口一律静默给空操作，避免窗口装配时因缺方法而崩
        return _noop


def _noop(*_a, **_k):
    return None