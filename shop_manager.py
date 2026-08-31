# 店铺管理模块 - 从 main_qt.py 提取
import os

from PyQt6.QtWidgets import (QDialog, QLineEdit, QMenu, QTabBar,
                             QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
                             QListWidget, QListWidgetItem, QGraphicsDropShadowEffect)
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QIcon, QColor

from ui_widgets import (CustomButton as _CustomButton, SoftButton as _SoftButton,
                        PainterTextLabel as _PainterTextLabel, ask_confirm, msg_warn)

try:
    import database
    HAS_DB = True
except:
    HAS_DB = False


class ShopManager:
    """店铺管理：增删改查、启动/停止。"""

    def __init__(self, main_window):
        self.main_window = main_window  # 主窗口实例（FireBrowser）
        self._tab_shop = {}  # 顶部标签栏：tab索引 -> 店铺数据

    def _get_shop_id(self, shop):
        """安全获取店铺ID：兼容dict/list两种格式"""
        if isinstance(shop, list):
            return shop[0].get('id', 0) if shop else 0
        return shop.get('id', 0) if isinstance(shop, dict) else 0

    def _find_open_tab_idx(self, shop_id):
        """通过店铺ID查找已打开的标签页索引，找不到返回None"""
        if not shop_id:
            return None
        for idx, tab in self.main_window.browser_tabs.items():
            tab_shop = getattr(tab, 'shop', None)
            if not tab_shop:
                continue
            if self._get_shop_id(tab_shop) == shop_id:
                return idx
        return None

    def _refresh_shops(self):
        """顶部店铺标签栏：只显示已打开的店铺（已登录）；未打开的店铺不出现在顶部，
        只能在"+"号列表里点"启动"打开。点标签=切到该店铺页面。
        添加/删除/编辑店铺或打开/关闭页面后刷新。重建时发信号被屏蔽，避免误操作。"""
        tabs = self.main_window.shop_tabs
        tabs.blockSignals(True)  # 重建过程不发切换信号，避免误打开店铺
        try:
            while tabs.count() > 0:  # QTabBar 没有 clear()，逐个移除标签
                tabs.removeTab(0)
            self._tab_shop.clear()
            if not HAS_DB:
                return
            for s in database.get_all_shops() or []:
                if self._find_open_tab_idx(self._get_shop_id(s)) is None:
                    continue  # 未打开的店铺不显示到顶部标签栏，只能在+号列表启动
                name = str(s.get('shop_name') or '未命名店铺').strip()
                idx = tabs.addTab(name)
                tabs.setTabToolTip(idx, name)
                self._tab_shop[idx] = s
        finally:
            tabs.blockSignals(False)
        # 同步选中：当前页面显示的店铺对应的标签高亮
        self.main_window._sync_shop_tab_selection(self.main_window.stack.currentWidget())
        # 无已打开店铺时左上角显示一键启动按钮（有店铺标签后自动隐藏）
        self.main_window._update_start_all_empty_btn()
        # 若店铺列表弹窗正开着，同步刷新它（启动/运行状态立刻更新，不用重开弹窗）
        self._refresh_shop_list_popup()

    def _refresh_shop_list_popup(self):
        """店铺列表弹窗正开着时，重建它的内容（每行启动/运行状态）。
        这样点「启动」后按钮马上变「运行中」，不用重新打开弹窗。"""
        w = getattr(self, '_shop_list_widget', None)
        if w is not None:
            try:
                self._fill_shop_list(w)
            except Exception:
                pass  # 弹窗正在关闭或控件已失效，忽略

    def _on_shop_tab_changed(self, idx):
        """点击顶部店铺标签：已打开的切过去；未打开的打开该店铺。"""
        if idx < 0:
            return
        shop = self._tab_shop.get(idx)
        if not shop:
            return
        tab_idx = self._find_open_tab_idx(self._get_shop_id(shop))
        if tab_idx is not None:
            self.main_window.stack.setCurrentIndex(tab_idx)
        else:
            self._open_shop_by_data(shop)

    def _store_context_menu(self, pos):
        """顶部店铺标签右键：编辑/删除该店铺。"""
        tab_bar = self.main_window.shop_tabs
        idx = tab_bar.tabAt(pos)
        if idx < 0:
            return
        shop = self._tab_shop.get(idx)
        if not shop:
            return
        menu = QMenu(self.main_window)
        menu.addAction("编辑店铺", lambda: self._edit_shop(shop))
        menu.addAction("删除店铺", lambda: self._delete_shop(shop))
        menu.exec(tab_bar.mapToGlobal(pos))

    def _fill_shop_list(self, list_widget):
        """把店铺列表填进浮层列表控件（样式同原左侧店铺列表）：
        每行店铺名 + 启动/运行状态按钮（行间带分隔线）。
        已打开的显示"运行中"（点击切过去），未打开的显示"启动"（点击打开）。"""
        list_widget.clear()
        if not HAS_DB:
            return
        asset_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons')
        for s in database.get_all_shops() or []:
            row = QWidget()
            row.setStyleSheet("border-bottom: 2px solid #bfdbfe; background: transparent;")
            row_l = QHBoxLayout(row)
            row_l.setContentsMargins(12, 2, 10, 2)
            row_l.setSpacing(0)
            name_lbl = QLabel(str(s.get('shop_name') or '未命名店铺'))
            name_lbl.setStyleSheet("font-size: 13px; color: #1e293b; border: none; background: transparent; padding: 0px;")
            name_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            row_l.addWidget(name_lbl)
            row_l.addStretch()
            shop_id = self._get_shop_id(s)
            is_running = self._find_open_tab_idx(shop_id) is not None
            btn = QPushButton()
            btn.setFixedSize(72, 34)
            img_path = os.path.join(asset_dir, '运行中.png' if is_running else '启动.png')
            if os.path.exists(img_path):
                btn.setIcon(QIcon(img_path))
                btn.setIconSize(QSize(68, 30))
                btn.setStyleSheet("""
                    QPushButton { background: transparent; border: none; padding: 0px; }
                    QPushButton:hover { background: rgba(59,130,246,0.08); border-radius: 6px; }
                """)
            else:
                btn.setText("●运行中" if is_running else "▶启动")
                btn.setStyleSheet("border: none; color: #3b82f6; font-size: 12px; background: transparent;")
            btn.clicked.connect(lambda checked, shop=s: self._on_start_btn(shop))
            row_l.addWidget(btn, 0, Qt.AlignmentFlag.AlignVCenter)
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, s)
            item.setSizeHint(QSize(0, 52))
            list_widget.addItem(item)
            list_widget.setItemWidget(item, row)

    def _on_start_btn(self, shop):
        """启动/运行按钮点击：已打开切过去，未打开打开该店铺页面。"""
        if not shop:
            return
        tab_idx = self._find_open_tab_idx(self._get_shop_id(shop))
        if tab_idx is not None:
            self.main_window.stack.setCurrentIndex(tab_idx)
        else:
            self._open_shop_by_data(shop)

    def _add_shop(self):
        self._edit_shop_dialog(None)

    def _edit_shop(self, shop):
        self._edit_shop_dialog(shop)

    def _edit_shop_dialog(self, shop):
        """添加/编辑店铺弹窗（白卡圆角+阴影+蓝色标题样式）。
        新增传空 shop，编辑传原店铺数据；保存后刷新顶部标签栏并刷新弹出的店铺列表。"""
        shop = shop or {}  # 编辑时传原店铺数据，新增传空
        is_edit = bool(shop)  # 传了店铺数据=编辑，空=新增
        d = QDialog(self.main_window)
        d.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
        d.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        d.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        # 外层容器：圆角白色卡片
        card = QWidget(d)
        card.setObjectName("card")
        card.setMinimumWidth(360)
        outer = QVBoxLayout(d)
        outer.setContentsMargins(40, 40, 40, 40)
        outer.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 24, 28, 24)
        card_layout.setSpacing(12)

        # 标题区：蓝色标题 + 灰色副标题
        title_label = _PainterTextLabel("编辑店铺" if is_edit else "添加店铺", color="#2563eb", font_size=16, bold=True)
        subtitle_label = _PainterTextLabel("填写店铺信息，保存后立即生效", color="#94a3b8", font_size=10)
        card_layout.addWidget(title_label)
        card_layout.addWidget(subtitle_label)
        card_layout.addSpacing(6)

        # 表单：每组 小标签 + 输入框
        def _mk_field(caption, placeholder):
            cap = _PainterTextLabel(caption, color="#94a3b8", font_size=10)
            edit = QLineEdit()
            edit.setPlaceholderText(placeholder)
            edit.setStyleSheet("""
                QLineEdit {
                    border: 1px solid #d1d5db; border-radius: 8px;
                    padding: 0 10px; font-size: 13px; color: #1e293b;
                    background: #ffffff;
                }
                QLineEdit:focus { border: 1px solid #2563eb; }
            """)
            edit.setFixedHeight(38)
            return cap, edit

        cap_name, inp_name = _mk_field("店铺名称*", "必填")
        inp_name.setText(shop.get('shop_name', ''))
        cap_user, inp_user = _mk_field("主账号", "选填")
        inp_user.setText(shop.get('user_name', ''))
        cap_pwd, inp_pwd = _mk_field("密码", "选填")
        inp_pwd.setText(shop.get('password', ''))
        inp_pwd.setEchoMode(QLineEdit.EchoMode.Password)

        form = QVBoxLayout()
        form.setSpacing(6)
        for cap, edit in ((cap_name, inp_name), (cap_user, inp_user), (cap_pwd, inp_pwd)):
            form.addWidget(cap)
            form.addWidget(edit)
        card_layout.addLayout(form)
        card_layout.addSpacing(10)

        # 按钮：保存（主蓝）+ 取消（次灰）
        btn_save = _CustomButton("保存", bg="#2563eb", fg="#ffffff", height=42, radius=10, font_size=14)
        btn_save.clicked.connect(lambda: self._save_shop_edit(d, shop, inp_name, inp_user, inp_pwd))
        btn_cancel = _SoftButton("取消", bg="#eef2f7", fg="#475569", height=42, radius=10, font_size=13)
        btn_cancel.clicked.connect(d.reject)
        btns = QHBoxLayout()
        btns.setSpacing(10)
        btns.addWidget(btn_cancel, stretch=1)
        btns.addWidget(btn_save, stretch=1)
        card_layout.addLayout(btns)

        # 阴影（白卡圆角）
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(60)
        shadow.setXOffset(0)
        shadow.setYOffset(16)
        shadow.setColor(QColor(30, 58, 138, 50))
        card.setGraphicsEffect(shadow)

        d.setStyleSheet("""
            #card { background-color: white; border-radius: 16px; }
        """)
        d.exec()

    def _save_shop_edit(self, dlg, old_shop, name, user, pwd):
        name = name.text().strip()
        user = user.text().strip()
        pwd = pwd.text().strip()
        if not name:
            msg_warn(dlg, "提示", "店铺名称不能为空"); return
        data = {'shop_name': name, 'user_name': user, 'password': pwd}
        if HAS_DB:
            if old_shop:
                database.update_shop(old_shop.get('id', 0), data)
            else:
                database.add_shop(data)
        dlg.accept()
        self._refresh_shops()  # 刷新顶部标签栏，并顺带刷新开着的店铺列表弹窗

    def _delete_shop(self, shop):
        if not shop:
            return
        if ask_confirm(self.main_window, "确认", f"删除 \"{shop.get('shop_name', '')}\"?"):
            if HAS_DB:
                database.delete_shop(shop.get('id', 0))
            self._refresh_shops()

    def _close_tab(self, idx):
        if idx in self.main_window.browser_tabs:
            self.main_window.browser_tabs[idx].close_browser()
            del self.main_window.browser_tabs[idx]
        self.main_window._stack_names.pop(idx, None)
        self.main_window.stack.removeWidget(self.main_window.stack.widget(idx))
        # 刷新顶部店铺标签栏
        self._refresh_shops()

    def _start_all(self):
        try:
            if not HAS_DB:
                msg_warn(self.main_window, "提示", "数据模块未加载，请检查数据库文件后重启软件")
                return
            shops = database.get_all_shops()
            if not shops:
                msg_warn(self.main_window, "提示", "还没有添加店铺，请先添加店铺后再启动")
                return
            print(f"【启动诊断】准备启动 {len(shops)} 个店铺页面...")
            try:
                self.main_window._log_to_diag_window(f"[启动] 准备启动 {len(shops)} 个店铺页面...")
            except Exception:
                pass
            self._launch_next_shop(0, shops)
            # 批量登录期间先隐藏顶部轨迹条，避免乱窜；全部登录完后恢复显示
            self.main_window.shop_tabs.setIndicatorHidden(True)
        except Exception as e:
            import traceback as _tb
            err_txt = f"启动店铺出错：{e}\n{_tb.format_exc(limit=3)}"
            print(f"【启动失败】{err_txt}", flush=True)
            try:
                self.main_window._log_to_diag_window(f"[启动失败] {err_txt}")
            except Exception:
                pass
            try:
                msg_warn(self.main_window, "启动出错", f"店铺启动遇到问题：{e}")
            except Exception:
                pass

    def _launch_next_shop(self, index, shops):
        if index >= len(shops):
            # 所有标签页创建完毕
            # 批量登录结束：恢复显示顶部轨迹条
            try:
                self.main_window.shop_tabs.setIndicatorHidden(False)
            except Exception:
                pass
            # 恢复浏览器静音状态
            QTimer.singleShot(3000, self.main_window._apply_startup_mute)
            # 自动开启监控（崩溃恢复模式下按上次开关状态，正常启动默认开）
            target = getattr(self.main_window, '_auto_monitor_state', None)
            QTimer.singleShot(500, lambda: self.main_window.set_monitoring(target if target is not None else True))
            try:
                self.main_window._log_to_diag_window(f"[启动] 全部 {len(shops)} 个店铺启动流程已结束")
            except Exception:
                pass
            return
        s = shops[index]  # 当前要启动的店铺数据
        shop_name = s.get('shop_name', f'店铺{index+1}')
        print(f"【启动诊断】正在启动第 {index+1} 个店铺: {shop_name}")
        try:
            self.main_window._log_to_diag_window(f"[启动] 正在打开第 {index+1}/{len(shops)} 个店铺: {shop_name}")
        except Exception:
            pass
        try:
            # 批量启动时：第一个店铺显示到最前，后面的都留在后台（不抢焦点）
            self._open_shop_by_data(s, front=(index == 0))
        except Exception as e:
            err_txt = f"第 {index+1} 个店铺({shop_name})启动失败: {e}"
            print(f"【启动诊断】{err_txt}", flush=True)
            try:
                self.main_window._log_to_diag_window(f"[启动失败] {err_txt}")
            except Exception:
                pass
        # 无论当前成功失败，继续启动下一家（间隔保持2.5秒）
        QTimer.singleShot(2500, lambda: self._launch_next_shop(index+1, shops))

    def _open_shop_by_data(self, shop, front=True):
        # 延迟导入避免循环依赖
        from main_qt import BrowserTab
        import traceback

        shop_name = shop.get('shop_name', '未命名店铺') if isinstance(shop, dict) else '未命名店铺'
        shop_id = self._get_shop_id(shop)

        try:
            # 检查是否已打开，已打开则直接切换（用店铺ID判断，避免店名前6字重复导致误判）
            idx = self._find_open_tab_idx(shop_id)
            if idx is not None:
                if front:
                    self.main_window.stack.setCurrentIndex(idx)
                return
            tab = BrowserTab(shop, log_callback=self.main_window._log_to_window, diag_callback=self.main_window._log_to_diag_window)  # 创建店铺标签页
            # 如果主开关已开启，新标签页自动继承
            if self.main_window.monitoring:
                tab._set_monitoring(True)
            # 继承浏览器静音状态
            if self.main_window._browser_muted:
                try:
                    tab.web.page().setAudioMuted(True)
                except:
                    pass
            idx = self.main_window.stack.addWidget(tab)
            self.main_window.browser_tabs[idx] = tab
            self.main_window._stack_names[idx] = shop['shop_name'][:6] if isinstance(shop, dict) else ''
            # 保持页面可见，防止后台标签页被 Chromium 限制
            try:
                tab.web.page().setPageVisible(True)
            except:
                pass
            # 仅当要求显示到最前时才切换过去；批量启动时后面的店铺留在后台
            if front:
                self.main_window.stack.setCurrentIndex(idx)
            # 店铺显示/隐藏由容器统一管理（只显示当前、其余隐藏），见 OverlayContainer；
            # 不再需要手动纠正原生窗口 Z 序（叠放方案已由 hide/show 取代）。
            # 延迟刷新店铺列表（避免按钮销毁中断加载流程）
            QTimer.singleShot(100, self._refresh_shops)
        except Exception as e:
            err_detail = traceback.format_exc(limit=2)
            print(f"【启动失败】{shop_name}: {e}\n{err_detail}", flush=True)
            # 把失败信息也写到诊断窗口方便排查
            try:
                if hasattr(self.main_window, '_log_to_diag_window'):
                    self.main_window._log_to_diag_window(f"[启动失败] {shop_name}: {e}")
            except:
                pass
            msg_warn(self.main_window, "启动失败", f"店铺「{shop_name}」打开失败：{e}")

    def _stop_all(self):
        self.main_window.monitoring = False  # 关闭总开关
        self.main_window._sync_monitoring_to_tabs()  # 同步所有标签页
        for idx in list(self.main_window.browser_tabs.keys()):
            self._close_tab(idx)  # 逐个关闭店铺标签页
        self.main_window._log_to_diag_window("全部已停止")
