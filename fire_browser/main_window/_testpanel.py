from fire_browser.main_window._deps import *

class _TestPanel:
    # 主窗口零件：@testpanel（方法来自 main_qt.py 的 FireBrowser，按功能归位，非新增逻辑）

    def _test_on(self, name):
        """测试模式：指定功能模块的开关是否打开。非测试模式恒返回True，所有功能照常。"""
        if not getattr(self, '_test_mode', False):
            return True
        return bool(getattr(self, '_test_switches', {}).get(name, False))

    def _create_test_panel(self):
        """测试模式开关面板：8个功能模块各一个勾选框，默认全关，逐个勾选定位卡死元凶。
        独立小窗（工具窗+置顶），不占主界面布局，关闭主窗口时随之销毁。"""
        try:
            panel = QWidget(None, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
            panel.setWindowTitle('测试开关（默认全关）')
            lay = QVBoxLayout(panel)
            lay.setContentsMargins(10, 10, 10, 10)
            tip = QLabel('逐个勾选模块定位卡死元凶\n每次勾选都写入运行日志')
            lay.addWidget(tip)
            for _name in _TEST_MODULES:
                _cb = QCheckBox(_name)
                _cb.setChecked(False)
                _cb.toggled.connect(lambda on, n=_name: self._on_test_toggle(n, on))
                lay.addWidget(_cb)
            self._test_panel = panel
            # 贴在主窗口右上角外侧，不遮主界面
            panel.move(self.x() + self.width() + 12, self.y())
            panel.show()
        except Exception as e:
            self._log_to_window(f"[测试模式] 开关面板创建失败: {e}")

    def _on_test_toggle(self, name, on):
        """勾选/取消模块开关：更新状态 + 运行日志/诊断日志各留一行（卡死时按最后记录定位当时开着的模块）"""
        self._test_switches[name] = bool(on)
        line = f"[测试] {'开启' if on else '关闭'}：{name}"
        try:
            self._log_to_window(line)
            _write_diag_file(f"{datetime.now().strftime('%H:%M:%S')} {line}")
        except Exception:
            pass
