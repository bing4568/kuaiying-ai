from fire_browser.main_window._deps import *

class _Switch:
    # 主窗口零件：@switch（方法来自 main_qt.py 的 FireBrowser，按功能归位，非新增逻辑）

    def _on_tab_changed(self, idx):
        """切换标签页时的处理"""
        if idx < 0:
            return
        # 诊断：记录当前页被切换到了哪个店铺，并抓"是谁切的"（调用栈）用于排查批量启动后页面被切走
        try:
            _cur_tab = self.stack.widget(idx)
            if hasattr(_cur_tab, 'shop_name'):
                import traceback as _tb
                _stack = "".join(_tb.format_stack(limit=8)[:-1]).strip()
                _write_diag_file(f"[启动诊断] 当前页被切换→ {_cur_tab.shop_name} | 页号={idx}\n调用栈:\n{_stack}")
        except Exception:
            pass
        tab = self.stack.widget(idx)
        if not isinstance(tab, BrowserTab):
            return
        # 顶部店铺标签高亮跟随实际页面：页面切到哪家店铺，标签就高亮哪家
        self._sync_shop_tab_selection(tab)
        # 保持所有标签页的 WebEngine 页面可见，防止后台标签页被 Chromium 限制
        for i in range(self.stack.count()):
            w = self.stack.widget(i)
            if isinstance(w, BrowserTab):
                try:
                    w.web.page().setPageVisible(True)
                except:
                    pass  # 兼容旧版本 PyQt5

    def _sync_shop_tab_selection(self, tab):
        """顶部店铺标签高亮跟随实际页面：页面切到哪家店铺，标签就高亮哪家。
        页面切换有多个入口（点标签/一键启动等），标签高亮必须统一跟随实际页面。
        同步时屏蔽信号，避免触发"点击标签"逻辑造成循环。"""
        if not tab:
            return
        shop = getattr(tab, 'shop', None)
        if not shop:
            return
        try:
            shop_id = shop[0].get('id', 0) if isinstance(shop, list) and shop else (shop.get('id', 0) if isinstance(shop, dict) else 0)
        except Exception:
            return
        if not shop_id:
            return
        for idx, s in self._shop_mgr._tab_shop.items():
            try:
                sid = s[0].get('id', 0) if isinstance(s, list) and s else (s.get('id', 0) if isinstance(s, dict) else 0)
            except Exception:
                continue
            if sid == shop_id:
                self.shop_tabs.blockSignals(True)
                self.shop_tabs.setCurrentIndex(idx)
                self.shop_tabs.blockSignals(False)
                self.shop_tabs.sync_indicator()  # 程序侧切换：指示线平滑滑到该标签
                break

    def _on_toggle_clicked(self):
        """按钮点击入口：翻转状态后交给set_monitoring"""
        self._log_to_diag_window(f"■ [按钮] 点击，当前状态={self.monitoring}，翻转为{not self.monitoring}")
        self.set_monitoring(not self.monitoring)

    def set_monitoring(self, enabled):
        """显式设置自动回复开关状态（不翻转）。所有调用方统一走这里。"""
        if self.monitoring == enabled:
            self._log_to_diag_window(f"■ [开关] 状态已是{enabled}，跳过")
            return
        self.monitoring = enabled
        new_state = "ON" if enabled else "OFF"
        self._log_to_diag_window(f"■ [开关] 主开关 → {new_state}（标签页数:{self.stack.count()}）")
        # 同步到所有标签页（异常隔离，单个tab出错不影响其他）
        self._sync_monitoring_to_tabs()
        # 更新按钮图标
        self._update_toggle_icon(enabled)
        # 记录开关状态：崩溃恢复时按上次状态自动开关
        try:
            _state_path = os.path.join(_data_dir(), 'monitor_state.json')
            os.makedirs(os.path.dirname(_state_path), exist_ok=True)
            with open(_state_path, 'w', encoding='utf-8') as f:
                json.dump({'monitor': enabled}, f)
        except Exception:
            pass

    def _sync_monitoring_to_tabs(self):
        """将主开关状态同步到所有标签页（带异常保护）"""
        for idx, tab in list(self.browser_tabs.items()):
            shop_name = getattr(tab, 'shop_name', f'标签页{idx}')
            try:
                tab._set_monitoring(self.monitoring)
                self._log_to_diag_window(f"■ [同步] {shop_name} → {'ON' if self.monitoring else 'OFF'}")
            except Exception as e:
                self._log_to_diag_window(f"■ [警告] {shop_name}同步失败: {e}")

    def _update_toggle_icon(self, monitoring):
        """根据开关状态更新侧边栏按钮：开启→高亮+状态文字，关闭→恢复灰色+停止文字"""
        if not hasattr(self, '_btn_auto'):
            return
        if monitoring:
            self._btn_auto.setText("关闭自动回复")
            self._btn_auto.setActive(True)
            self._log_to_diag_window("[图标] 自动回复运行中（高亮）")
        else:
            self._btn_auto.setText("开启自动回复")
            self._btn_auto.setActive(False)
            self._log_to_diag_window("[图标] 自动回复已停止")
        # 同步顶栏左上角接待状态文字（AI接待中/停止接待）
        if hasattr(self, '_update_ai_status_label'):
            self._update_ai_status_label()

    def _refresh_pages_after_state_change(self):
        """窗口状态变化后延迟执行：确认已不在最小化状态时，才让各网页按最终尺寸直接重排/重画。
        不做"先还原再最大化"那种可见缩放，避免肉眼可见的闪动；靠精确的视口尺寸让网页内核重画。"""
        try:
            if self.isMinimized():
                return
        except Exception:
            return
        self._refresh_pages_on_restore()
        # 放大动画可能仍有残影，稍后再重拍一次兜底，确保网页内核用最终尺寸干净地重画一次。
        QTimer.singleShot(200, self._refresh_pages_on_restore)

    def _refresh_pages_on_restore(self):
        """窗口从最小化恢复（尤其最大化态）后，强制所有网页重新排版/重画。
        否则 QtWebEngine 沿用缩小前的旧画面，中间空白、左上角错位。"""
        for i in range(self.stack.count()):
            tab = self.stack.widget(i)
            if not isinstance(tab, BrowserTab):
                continue
            try:
                tab.web.page().setLifecycleState(QWebEnginePage.LifecycleState.LifecycleStateActive)
            except:
                pass
            try:
                tab.web.page().setPageVisible(True)
            except:
                pass
            # 强制对齐视口：告诉 Chromium 网页当前实际尺寸，避免它沿用最小化前的旧尺寸
            try:
                tab.web.page().setViewportSize(tab.web.size())
            except:
                pass
            # 强制重画：把网页宽度微调一个像素再还原，逼迫 QtWebEngine 刷新视口并重绘（不再用隐藏/显示，避免内容闪一下）
            try:
                w = tab.web
                g = w.geometry()
                if g.width() > 0:
                    w.setGeometry(g.x(), g.y(), g.width() - 1, g.height() - 1)
                    w.setGeometry(g)
            except:
                pass
            try:
                tab.web.update()
            except:
                pass
