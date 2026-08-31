from fire_browser.main_window._deps import *


class _Login:
    # 主窗口零件：@login（开源版已无账号体系，登录相关逻辑全部移除，仅保留方法占位。）

    def _check_login(self):
        """启动检查登录：开源版已简化，无账号体系，直接进入主界面。"""
        return

    def _show_login_dialog(self, server_url):
        """开源版无登录/注册流程，空实现（仅为兼容旧调用）"""
        return

    def _background_keepalive(self):
        """开源版无后台保活逻辑，空实现（兼容心跳定时器调用）"""
        return