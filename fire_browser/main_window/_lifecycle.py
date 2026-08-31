from fire_browser.main_window._deps import *

class _Lifecycle:
    # 主窗口零件：@lifecycle（方法来自 main_qt.py 的 FireBrowser，按功能归位，非新增逻辑）

    def _do_logout(self):
        """退出登录：清除登录信息，保留其他配置"""
        try:
            self._do_logout_inner()
        except Exception as _e:
            import traceback as _tb
            _write_diag_file(f"[LOGOUT] 退出登录异常: {_e!r}\n{_tb.format_exc()}")

    def _do_logout_inner(self):
        from config_manager import ConfigManager
        server_url = ConfigManager.instance().get('auth', 'server_url', fallback='')
        ConfigManager.instance().set_many([
            ('auth', 'token', ''),
            ('auth', 'username', ''),
            ('auth', 'server_url', server_url),
        ])
        self.statusBar().clearMessage()
        self.statusBar().showMessage("未登录")
        QApplication.processEvents()
        self._show_login_dialog(server_url)

    def _show_toast(self, text, duration=2200):
        """自动渐隐提示：无边框、不抢焦点、窗口居中、几秒后淡出消失"""
        try:
            from PyQt6.QtWidgets import QLabel
            from PyQt6.QtCore import QPropertyAnimation
            tip = QLabel(text, None)
            tip.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
            tip.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
            tip.setStyleSheet(
                "QLabel{background:#323232;color:#ffffff;border-radius:14px;"
                "padding:10px 18px;font-size:13px;font-family:'Microsoft YaHei';}")
            tip.adjustSize()
            pg = self.geometry()
            tip.move(pg.x() + (pg.width() - tip.width()) // 2,
                     pg.y() + (pg.height() - tip.height()) // 2)
            tip.show()
            anim = QPropertyAnimation(tip, b"windowOpacity")
            anim.setDuration(600)
            anim.setStartValue(1.0)
            anim.setEndValue(0.0)
            anim.finished.connect(tip.deleteLater)
            tip._anim = anim  # 防止动画对象被回收
            QTimer.singleShot(duration, anim.start)
        except Exception:
            pass

    # 开源演示版：原"旧库存/待补充库清洗"业务已移除（仅保留店铺库初始化）
    def _init_db(self):
        if HAS_DB:
            try:
                database.init_database()
            except: pass

    def _log_to_window(self, text):
        self._log_mgr.log_to_window(text)

    def _log_to_diag_window(self, text):
        """诊断日志弹窗已移除：AI服务日志（带[AI]前缀）转发到运行日志面板，方便直接看到真实原因"""
        if text.startswith('[AI]'):
            self._log_mgr.log_to_window(text)

    def _open_msg_log(self):
        """更多功能→消息日志：弹出查看记录"""
        if self._msg_log_dialog:
            self._msg_log_dialog.show()
            self._msg_log_dialog.raise_()
            self._msg_log_dialog.activateWindow()

    def _log_net(self, text):
        """网络日志弹窗已移除，此方法保留仅防调用报错"""
        pass

    def _show_from_tray(self):
        """从托盘恢复窗口：显示并激活（保留最大化状态），并刷新各网页防止画面错位/空白。"""
        self.show()
        self.activateWindow()
        self.raise_()
        # 隐藏→显示后窗口状态可能不变，changeEvent 不一定会触发，这里主动刷新一遍网页，
        # 兜底确保网页内核用最新尺寸重新渲染，避免沿用隐藏前的旧画面。
        self._refresh_pages_on_restore()

    def _check_update(self):
        self._updater.check_update()

    def _on_update_status(self, text):
        if text:
            self._update_status_label.setText(text)
            self._update_status_label.show()
        else:
            self._update_status_label.hide()

    @pyqtSlot()
    def _apply_update(self):
        self._updater.apply_update()

    def _update_failed(self, msg):
        self._update_status_label.hide()
        msg_warn(self, "更新失败", msg)

    def _real_quit(self):
        self._quitting = True
        # 登录框若还开着，一并关掉，保证整体退出（不会出现"软件退了登录页还在"）
        try:
            if self._login_dlg is not None:
                self._login_dlg.reject()
                self._login_dlg = None
        except Exception:
            pass
        self._tray_icon.hide()
        self.close()  # 会走 closeEvent，那里已写"程序正常退出"留痕
