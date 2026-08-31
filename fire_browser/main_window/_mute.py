from fire_browser.main_window._deps import *

class _Mute:
    # 主窗口零件：@mute（方法来自 main_qt.py 的 FireBrowser，按功能归位，非新增逻辑）

    def _toggle_mute(self):
        """切换浏览器静音"""
        self._browser_muted = not self._browser_muted
        self._apply_mute_to_all_tabs()
        self._log_to_diag_window(f"浏览器已{'静音' if self._browser_muted else '取消静音'}")
        self._save_mute_state()
        # 更新侧边静音按钮文字与图标
        self._refresh_mute_button()
        # 居中渐隐提示：浏览器内核限制，重启后才完全生效
        self._show_toast("浏览器声音已%s，重启软件后生效。" % ('关闭' if self._browser_muted else '开启'))

    def _refresh_mute_button(self):
        """刷新侧边栏声音按钮，使其显示与当前静音状态一致（含启动时按上次状态初始化）"""
        if not hasattr(self, '_btn_mute'):
            return
        base_dir_ = PROJECT_ROOT
        if self._browser_muted:
            self._btn_mute.setText("已静音")
            self._btn_mute.setIconPath(os.path.join(base_dir_, 'icons', '静音.png'))
        else:
            self._btn_mute.setText("浏览器声音")
            self._btn_mute.setIconPath(os.path.join(base_dir_, 'icons', '声音开启.png'))

    def _apply_mute_to_all_tabs(self):
        """对所有标签页应用当前静音状态"""
        for i in range(self.stack.count()):
            tab = self.stack.widget(i)
            if isinstance(tab, BrowserTab):
                try:
                    tab.web.page().setAudioMuted(self._browser_muted)
                except:
                    pass

    def _save_mute_state(self):
        """保存浏览器静音状态（统一走配置管家：内存+原子落盘）"""
        try:
            from config_manager import ConfigManager
            ConfigManager.instance().set('general', 'browser_muted', '1' if self._browser_muted else '0')
        except Exception as e:
            print(f"[Config] 保存静音状态失败: {e}", flush=True)

    def _load_mute_state(self):
        """从配置加载浏览器静音状态"""
        try:
            from config_manager import ConfigManager
            return ConfigManager.instance().get('general', 'browser_muted', fallback='0') == '1'
        except Exception:
            return False

    def _apply_startup_mute(self):
        """启动时对所有标签页应用静音状态"""
        if not self._browser_muted:
            return
        self._apply_mute_to_all_tabs()

        # 保持后台标签页活跃
        current = self.stack.currentIndex()
        for idx in range(self.stack.count()):
            if idx == current: continue
            tab = self.stack.widget(idx)
            if isinstance(tab, BrowserTab) and tab.monitoring:
                tab.web.page().runJavaScript("""
                    window.dispatchEvent(new Event('focus'));
                    fetch('https://mms.pinduoduo.com/', {method:'HEAD',cache:'no-store'}).catch(function(){});
                """)
