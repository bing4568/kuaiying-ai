from fire_browser.main_window._deps import *

class _Settings:
    # 主窗口零件：@settings（方法来自 main_qt.py 的 FireBrowser，按功能归位，非新增逻辑）

    def _show_reply_settings(self, jump_page=None):
        """打开设置中心（单例复用：对话框/视图/页面首次创建后永久复用，只显示/隐藏+重载数据，
        页面永不再移动/销毁——彻底消除"页面销毁瞬间撞上JS回调"的卡死根源）"""
        html_path = os.path.join(PROJECT_ROOT, 'reply-settings-center.html')
        self._rsc_jump = jump_page
        _write_diag_file('[设置中心] 打开请求进入 jump=%s' % jump_page)
        if getattr(self, '_rsc_dlg', None) is None:
            # 首次：创建整套设置中心（对话框+视图+页面+信号接线），内部已触发首次页面加载
            if not os.path.exists(html_path):
                msg_warn(self, "错误", "设置中心页面文件不存在")
                return
            self._build_rsc_dialog_once(html_path)
        else:
            # 重复打开：只清旧浮层+重载数据页。
            # ⚠️两条铁律（2026-08-28 排查"关闭后打不开"定位）：
            #   ①绝不能 disconnect titleChanged 等信号——那是页面的指令通道，断开后页面变哑巴，
            #     初始化/保存/关闭指令全部失联，窗口再也开不出来；
            #   ②重载必须走 self._rsc_bridge._reload_page()（旧代码调用的 _rsc_load 方法已被删，是悬空引用）
            web = self._rsc_web
            _old_mask = getattr(self, '_rsc_mask', None)
            if _old_mask is not None:
                try:
                    _old_mask.deleteLater()
                except Exception:
                    pass
            self._rsc_mask = _attach_loading_mask(web, "正在打开设置中心…")
            QTimer.singleShot(15000, self._rsc_mask_timeout)
            self._rsc_bridge._reload_page()
        _write_diag_file('[设置中心] show前 dlg可见=%s' % self._rsc_dlg.isVisible())
        # 每次打开都重新对齐主窗口当前位置和大小（主窗口挪动/最大化后弹老位置的问题）
        _nrect = _native_window_rect(self)
        self._rsc_dlg.setGeometry(QRect(*_nrect) if _nrect else self.frameGeometry())
        self._rsc_dlg.show()
        _write_diag_file('[设置中心] exec进入')
        _code = self._rsc_dlg.exec()
        _write_diag_file('[设置中心] exec返回 code=%s 窗口还可见=%s' % (_code, self._rsc_dlg.isVisible()))
        # 任何一条关闭路径走完后，都把主窗口顶回前台
        QTimer.singleShot(0, self._raise_main_window)

    def _rsc_mask_timeout(self):
        """15秒兜底：强制收走"正在打开设置中心"浮层（慢网络下页面晚点就绪也不永久遮挡）"""
        web = getattr(self, '_rsc_web', None)
        _m = getattr(web, '_loading_mask', None) if web is not None else None
        if _m is not None:
            try:
                web._loading_mask = None
                _m.dismiss()
            except Exception:
                pass

    def _build_rsc_dialog_once(self, html_path):
        """创建设置中心（仅首次调用）：对话框+视图+页面+全部信号接线，此后永久复用"""
        bridge = ReplySettingsBridge(self)
        self._rsc_bridge = bridge  # 存到实例：重复打开时重载数据页用（bridge._reload_page）

        dlg = QDialog(self)
        dlg.setWindowTitle("设置中心")
        self._rsc_dlg = dlg
        # 无边框（页面自带顶栏和关闭按钮，不叠加系统边框），铺满并覆盖整个主程序窗口
        dlg.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        _nrect = _native_window_rect(self)
        dlg.setGeometry(QRect(*_nrect) if _nrect else self.frameGeometry())

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(0, 0, 0, 0)

        web = QWebEngineView(dlg)
        _rpb = globals().get('_PREBUILT_RSC_PAGE')
        if _rpb is not None:
            # 复用启动时预建的内核配置与页面（规避"主窗口可见后再创建必崩"的踩坑）；
            # 页面被新窗口接管后，旧窗口的僵尸轮询自动停止。
            # 接管前先停止旧视图的在途加载：避免"页面搬家的瞬间撞上还没飞完的JS回调"
            # （回调在页面销毁过程中被触发，会在内核回调边界引发原生异常——2026-08-28 取证定位）
            _old_view = getattr(self, '_rsc_current_view', None)
            if _old_view is not None:
                try:
                    _old_view.page().stop()
                except Exception:
                    pass
            web.setPage(_rpb[1])
            self._rsc_current_view = web
        else:
            web.setPage(QWebEnginePage(QWebEngineProfile('settings_center', web), web))
            self._rsc_current_view = web
        # 防冻结保险（与店铺标签页同款）：告诉内核页面永远活跃可见。
        # 否则页面被"加载中"浮层盖住时内核会把页面冻住——页面发不出任何信号，
        # 浮层等不到"初始化完成"永不消失，表现为设置中心打开就卡死
        try:
            web.page().setLifecycleState(QWebEnginePage.LifecycleState.LifecycleStateActive)
        except Exception:
            pass  # 兼容旧版内核
        try:
            web.page().setPageVisible(True)
        except Exception:
            pass
        # 卡死取证：记录设置中心视图/页面销毁时刻
        web.destroyed.connect(lambda *_: _write_diag_file('[视图销毁] 设置中心网页控件已销毁'))
        try:
            web.page().destroyed.connect(lambda *_: _write_diag_file('[视图销毁] 设置中心页面对象已销毁'))
        except Exception:
            pass
        # 设置中心专用：把用户数据目录登记成内部网址（Edge 官方做法），页面由此能显示本地图片
        # （商品图缓存/图片回复/尺码表全在该目录下）；只作用于本窗口，不影响登录和店铺页面
        web.mapVirtualHost('kuaai-assets.example', _data_dir())
        layout.addWidget(web)
        # 禁用浏览器自带的英文右键菜单（页面已自绘中文右键菜单）
        web.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        # 加载中浮窗：飘在页面上方（Edge 空域盖不住），加载完成自动消失
        _attach_loading_mask(web, "正在打开设置中心…")

        # 浮层兜底：就算"初始化完成"信号被内核冻丢，最多15秒也强制收走浮层，保证窗口能点能关
        # （15秒：数据改在后台线程取，慢网络下页面会晚点就绪，避免浮层提前消失露出白屏）
        def _mask_timeout():
            _m = getattr(web, '_loading_mask', None)
            if _m is not None:
                web._loading_mask = None
                _m.dismiss()
        QTimer.singleShot(15000, _mask_timeout)

        # 提前创建对话框与网页控件的原生窗口：显示瞬间不再触发原生窗口重建，
        # 消除"打开瞬间 Hide→Show 循环 + 模态秒退"（2026-08-28 成分拆解实验定位）
        dlg.winId()
        web.winId()

        # Win11 系统圆角（与主程序同款），Win10 自动跳过
        _apply_win11_rounded(dlg)

        bridge._dlg = dlg  # 导出/导入配置时系统文件框的父窗口
        bridge._rsc_web = web  # "扫描商品"等异步任务完成后回调页面用
        self._rsc_web = web  # 存到实例：重复打开时清旧浮层/挂新浮层用

        def _load_page(reload_page=True):
            """（重新）加载设置中心页面并注入最新真实数据（导入配置/保存回复后调用它刷新页面）。
            取数据（联网拉模型列表+读库+图片换链）全在后台线程做——曾因网络卡顿在主线程
            干等（DNS 卡住时连超时都兜不住），点开设置中心整个程序冻死；构建完成经信号
            回主线程再加载页面，窗口秒开不卡。
            reload_page=False：保存回复后的"静默重建"模式——只把最新数据重新写进页面文件
            （让 F5/右键刷新能读到最新数据），不重载当前界面、不打断用户操作。"""
            def _build_bg():
                _ok = False
                _html = ''
                try:
                    with open(html_path, 'r', encoding='utf-8') as f:
                        _html = f.read()
                    # 把软件里的真实数据注入页面（替换 null 赋值行；</ 转义防破坏脚本）
                    try:
                        # 模型列表/PRO状态只在"整页打开/刷新"时联网拉取；
                        # 保存回复后的静默重建走缓存（毫秒级，不卡 F5 刷新）
                        if reload_page or bridge._rsc_models_cache is None:
                            bridge._rsc_models_cache = json.loads(bridge.get_model_options())
                        _mo = bridge._rsc_models_cache or {}
                        data_pack = {
                            'settings': json.loads(bridge.get_all_settings()),
                            'persona_list': json.loads(bridge.get_persona_list()),
                            'user_profile': json.loads(bridge.get_user_profile()),
                            'models': _mo.get('models', []),
                            'pro_unlocked': bool(_mo.get('pro_unlocked', False)),
                            'free_model': _mo.get('free_model', ''),
                            'replies': json.loads(bridge.get_general_replies()),
                            'products': json.loads(bridge.get_products()),
                            'product_replies': json.loads(bridge.get_product_replies()),
                        }
                        data_js = json.dumps(data_pack, ensure_ascii=False).replace('</', '<\\/')
                        _html = _html.replace('window.__RSC_DATA__ = null;',
                                              'window.__RSC_DATA__ = ' + data_js + ';')
                        # 告诉页面用户数据目录位置（换算本地图片为内部网址 kuaai-assets.example 用）
                        _html = _html.replace('window.__RSC_LOCAL_DIR__ = null;',
                                              'window.__RSC_LOCAL_DIR__ = ' + json.dumps(_data_dir().replace('\\', '/')) + ';')
                    except Exception:
                        pass
                    # 打开时直接跳到指定页；
                    # 每次构建时实时读 self._rsc_jump（⚠️不能引用外层不存在的 jump_page 变量——
                    # 代码拆分后悬空引用会 NameError，整个页面文件构建静默失败，2026-08-28 修复）
                    if getattr(self, '_rsc_jump', ''):
                        _html = _html.replace('window.__RSC_JUMP__ = null;',
                                              'window.__RSC_JUMP__ = ' + json.dumps(self._rsc_jump) + ';')
                    else:
                        _last_pg = ''
                        try:
                            from config_manager import ConfigManager as _CM5
                            _last_pg = _CM5.instance().raw().get('ui', 'rsc_last_page', fallback='')
                        except Exception as _e5:
                            _last_pg = ''
                            _write_diag_file('[设置中心][页签记忆] 读配置失败: %s' % _e5)
                        if _last_pg:
                            _needle = 'window.__RSC_LAST_PAGE__ = null;'
                            if _needle in _html:
                                _html = _html.replace(_needle,
                                                      'window.__RSC_LAST_PAGE__ = ' + json.dumps(_last_pg) + ';')
                                _write_diag_file('[设置中心][页签记忆] 构建页面：已注入上次页签=%s' % _last_pg)
                                # 治本防闪：浏览器边读边画，等文件末尾的切换脚本生效前，
                                # 写死选中的"商品个性回复"菜单已经被画出来（闪一下再切走）。
                                # 这里把"选中状态+显示哪页"直接改写进文件本体，首帧就是正确页签。
                                if ('data-page="%s"' % _last_pg) in _html:
                                    _html = _html.replace(
                                        'class="nav-item active" data-page="product-personality-reply"',
                                        'class="nav-item" data-page="product-personality-reply"')
                                    _html = _html.replace(
                                        'class="nav-item" data-page="%s"' % _last_pg,
                                        'class="nav-item active" data-page="%s"' % _last_pg)
                                    _html = _html.replace(
                                        '<section class="page hidden" id="page-%s">' % _last_pg,
                                        '<section class="page" id="page-%s">' % _last_pg)
                                else:
                                    _write_diag_file('[设置中心][页签记忆] 警告：注入的页签 %s 在菜单里不存在，跳过静态改写' % _last_pg)
                            else:
                                _write_diag_file('[设置中心][页签记忆] 构建页面：警告：HTML里找不到占位符（模板版本不对？）')
                        else:
                            # 新用户（从未记录过页签）：默认进"通用设置"；点过任何页签后就记住用户自己的选择
                            _last_pg = 'general-settings'
                            _write_diag_file('[设置中心][页签记忆] 配置里没有记录：新用户默认进通用设置')
                    # Edge 官方做法：把注入好数据的页面写进已登记的用户数据目录，再以内部网址打开。
                    # （直接打开本地文件会被内核当"下载"弹窗；内部网址方式正常显示且能读目录内图片）
                    _page_file = os.path.join(_data_dir(), 'settings_center_page.html')
                    # 原子写：先写临时文件再替换，防止"刷新正在读、保存正在写"时读到半截文件。
                    # 临时文件名带线程编号，防止两个后台重建线程（如同时保存商品+通用回复）抢同一个文件
                    _tmp = '%s.tmp%d' % (_page_file, threading.get_ident())
                    with open(_tmp, 'w', encoding='utf-8') as f:
                        f.write(_html)
                    os.replace(_tmp, _page_file)
                    _ok = True
                    if not reload_page:
                        _write_diag_file('[设置中心][页签记忆] 页面文件静默重建完成（磁盘已是最新）')
                except Exception:
                    pass
                bridge._rsc_last_html = _html  # 留给回退方式用（写文件失败时整页塞给浏览器）
                if reload_page:  # 静默重建（保存后同步文件）不重载当前界面，只保证磁盘文件是最新
                    bridge._page_file_ready.emit(_ok)
            threading.Thread(target=_build_bg, daemon=True).start()

        # 后台构建完成 → 主线程加载页面（窗口已先弹出，此步只换内容不卡界面）
        def _open_built_page(file_ok):
            try:
                if file_ok:
                    # 带时间戳参数避免内核缓存旧页面（保存/导入后刷新要看到最新数据）
                    web.load(QUrl('kuaai://kuaai-assets.example/settings_center_page.html?v=' + str(int(time.time() * 1000))))
                else:
                    # 写文件失败时退回原来的"整页塞给浏览器"方式，保证页面照常能开（仅本地图片不显示）
                    web.setHtml(getattr(bridge, '_rsc_last_html', '') or '', QUrl.fromLocalFile(html_path))
            except Exception:
                pass  # 窗口已关闭等场景：页面控件已销毁，忽略
        bridge._page_file_ready.connect(_open_built_page)

        _load_page()

        # 把刷新函数挂到桥接对象上：保存回复规则成功后重新加载页面，让网页快照与真实数据一致
        bridge._reload_page = _load_page
        # 保存回复/补充后：后台静默重建页面文件（不重载当前界面、不联网），
        # 让 F5/右键刷新能读到最新数据，不用重启软件
        bridge._regen_page_file = lambda: _load_page(reload_page=False)
        # 局部刷新：商品回复后台精修完成 / 通用回复保存后，只回传最新两份列表刷新对应区块，
        # 不再整页重建（避免重新联网拉模型列表 + 全量重载导致的保存卡顿）
        def _push_reply_lists():
            try:
                _b64 = base64.b64encode(bridge.get_general_replies().encode('utf-8')).decode('ascii')
                web.page().runJavaScript(
                    "window.__onRSCGeneralReply && window.__onRSCGeneralReply(decodeURIComponent(escape(atob('" + _b64 + "'))));"
                )
            except Exception:
                pass
            try:
                _b64 = base64.b64encode(bridge.get_product_replies().encode('utf-8')).decode('ascii')
                web.page().runJavaScript(
                    "window.__onRSCProductReplies && window.__onRSCProductReplies(decodeURIComponent(escape(atob('" + _b64 + "'))));"
                )
            except Exception:
                pass
        bridge._reload_requested.connect(lambda: _push_reply_lists())

        # 保存失败红字提示：后台任何保存入口失败 → 主线程推给页面顶部提示条（不再静默吞错）
        def _push_save_error(msg):
            try:
                _esc = str(msg).replace('\\', '\\\\').replace("'", "\\'").replace('\n', ' ')[:200]
                web.page().runJavaScript(
                    "window.__onRSCSaveError && window.__onRSCSaveError('" + _esc + "');"
                )
            except Exception:
                pass
        bridge._rsc_save_error.connect(lambda m: _push_save_error(m))

        # 待补充问题：读库挪到后台线程（曾因读库慢+内核冻页叠加导致打开卡死54秒），
        # 后台读完经信号回主线程推给页面刷新，主线程零等待
        def _push_missed(_b64):
            try:
                web.page().runJavaScript(
                    "window.__onRSCMissed && window.__onRSCMissed(decodeURIComponent(escape(atob('" + _b64 + "'))));"
                )
            except Exception:
                pass
        bridge._missed_ready.connect(_push_missed)

        def _fetch_missed_bg():
            def _work():
                try:
                    _b64 = base64.b64encode(bridge.get_missed().encode('utf-8')).decode('ascii')
                except Exception:
                    return
                bridge._missed_ready.emit(_b64)
            threading.Thread(target=_work, daemon=True).start()

        # 允许页面加载本地文件图片（商品图片已本地缓存，页面直接显示本地文件，秒开）
        # 本地页面访问文件权限由 QtWebEngine 内核统一管理（兼容层忽略该设置）

        # 网页通过修改页面标题发指令：RSC::方法::base64(参数)
        import base64, urllib.parse
        def _on_title_changed(title):
            if not title or not title.startswith('RSC::'):
                return
            parts = title.split('::', 2)
            method = parts[1] if len(parts) > 1 else ''
            raw = parts[2] if len(parts) > 2 else ''
            arg = None
            if raw:
                try:
                    arg = json.loads(urllib.parse.unquote(base64.b64decode(raw.encode('ascii')).decode('utf-8')))
                except Exception:
                    arg = None
            # 记录设置中心每次操作（方法 + 参数），测试期排查用
            _write_diag_file('[设置中心] 收到指令 method=%s arg=%s' % (
                method, json.dumps(arg, ensure_ascii=False)[:400] if arg is not None else str(raw)[:100]))
            if method == 'ready':
                # 页面初始化完成：缓0.2秒再收走"正在打开设置中心"浮层（留时间让画面上屏，避免闪跳）
                _m = getattr(web, '_loading_mask', None)
                if _m is not None:
                    web._loading_mask = None
                    QTimer.singleShot(200, _m.dismiss)
            elif method == 'remember_page' and isinstance(arg, dict):
                # 记住用户停留的页签（Qt 官方推荐做法：网页状态交给宿主软件保存，
                # 不依赖浏览器本地存储——自定义内部网址下 localStorage 写盘不可靠）。
                # 存进配置文件：刷新（页面文件重注入）/重开/重启软件都能回到这页。
                _pg = str(arg.get('page') or '')
                if _pg:
                    try:
                        from config_manager import ConfigManager as _CM6
                        _cfg6 = _CM6.instance().raw()
                        if not _cfg6.has_section('ui'):
                            _cfg6.add_section('ui')
                        _cfg6.set('ui', 'rsc_last_page', _pg)
                        _CM6.instance().save()
                        _write_diag_file('[设置中心][页签记忆] 已写入配置 ui.rsc_last_page=%s' % _pg)
                    except Exception as _e6:
                        _write_diag_file('[设置中心][页签记忆] 写配置失败: %s' % _e6)
                    # 静默重建设置中心页面文件，让 F5 刷新注入的"上次页签"是最新的（不重载当前界面）
                    try:
                        _regen = getattr(bridge, '_regen_page_file', None)
                        if callable(_regen):
                            _regen()
                            _write_diag_file('[设置中心][页签记忆] 已触发页面文件静默重建')
                        else:
                            _write_diag_file('[设置中心][页签记忆] 警告：_regen_page_file 不存在（页面还没构建完？）')
                    except Exception as _e6:
                        _write_diag_file('[设置中心][页签记忆] 静默重建异常: %s' % _e6)
            elif method == 'set_setting' and isinstance(arg, dict):
                bridge.set_setting(str(arg.get('key', '')), str(arg.get('value', '')))
            elif method == 'save_general_reply' and isinstance(arg, dict):
                bridge.save_general_reply(json.dumps(arg, ensure_ascii=False))
                _push_reply_lists()   # 保存后只回传最新列表刷新，不整页重建
            elif method == 'upsert_general_reply' and isinstance(arg, dict):
                bridge.upsert_general_reply(json.dumps(arg, ensure_ascii=False))
                _push_reply_lists()   # 保存后只回传最新列表刷新，不整页重建
            elif method == 'delete_general_reply' and isinstance(arg, dict):
                bridge.delete_general_reply(json.dumps(arg, ensure_ascii=False))
                _push_reply_lists()   # 删除后只回传最新列表刷新，不整页重建
            elif method == 'transfer_general_reply' and isinstance(arg, dict):
                bridge.transfer_general_reply(json.dumps(arg, ensure_ascii=False))
                _push_reply_lists()   # 转移后只回传最新列表刷新，不整页重建
            elif method == 'pick_reply_image':
                # 回复弹窗点「选择图片」：弹系统文件框 → 复制一份进程序 Picture 目录 → 回传新路径给页面预览
                _write_diag_file('[设置中心] 收到选图指令')
                try:
                    path, _f = QFileDialog.getOpenFileName(dlg, '选择图片', '',
                                                           '图片文件 (*.jpg *.jpeg *.png *.gif *.bmp *.webp)')
                    _write_diag_file('[设置中心] 文件框结果: %r' % path)
                    if path:
                        # 程序目录用绝对路径算，避免某些启动方式下拿到半截路径导致图片地址不完整
                        pic_dir = _pic_dir()
                        os.makedirs(pic_dir, exist_ok=True)
                        ext = os.path.splitext(path)[1].lower()
                        if ext not in ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'):
                            ext = '.jpg'
                        dest = os.path.join(pic_dir, 'reply_' + time.strftime('%Y%m%d_%H%M%S') + ext)
                        n = 1
                        while os.path.exists(dest):
                            dest = os.path.join(pic_dir, 'reply_%s_%d%s' % (time.strftime('%Y%m%d_%H%M%S'), n, ext))
                            n += 1
                        shutil.copy2(path, dest)
                        _write_diag_file('[设置中心] 图片已复制到: %s' % dest)
                        _b64 = base64.b64encode(dest.encode('utf-8')).decode('ascii')
                        # 回传新路径给页面，并同步查回页面状态（弹窗id、地址是否填上、有无报错）
                        web.page().runJavaScript(
                            "(function(){ try{ window.__onRSCPickImage && window.__onRSCPickImage('" + _b64 + "');"
                            " var m = window.__rtImageModal || '';"
                            " var el = m ? document.getElementById(m).querySelector('.rt-image-box .rt-image-path') : null;"
                            " return JSON.stringify({modal:m, val: el ? el.value : '', err:''});"
                            " }catch(e){ return JSON.stringify({err: String(e), stack: (e && e.stack) ? String(e.stack) : ''}); } })()",
                            lambda r: _write_diag_file('[设置中心] 回传后页面状态: %s' % (r,))
                        )
                        _write_diag_file('[设置中心] 已回传新路径给页面')
                except Exception as e:
                    _write_diag_file('[设置中心] 选图失败: %r' % e)
            elif method == 'pick_size_chart_image':
                # 配置尺码表点「上传图片」：弹系统文件框 → 复制一份进程序 Picture 目录 → 回传新路径给页面预览
                try:
                    path, _f = QFileDialog.getOpenFileName(dlg, '选择尺码表图片', '',
                                                           '图片文件 (*.jpg *.jpeg *.png *.gif *.bmp *.webp)')
                    if path:
                        pic_dir = _pic_dir()
                        os.makedirs(pic_dir, exist_ok=True)
                        ext = os.path.splitext(path)[1].lower()
                        if ext not in ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'):
                            ext = '.jpg'
                        dest = os.path.join(pic_dir, 'size_' + time.strftime('%Y%m%d_%H%M%S') + ext)
                        n = 1
                        while os.path.exists(dest):
                            dest = os.path.join(pic_dir, 'size_%s_%d%s' % (time.strftime('%Y%m%d_%H%M%S'), n, ext))
                            n += 1
                        shutil.copy2(path, dest)
                        _write_diag_file('[设置中心] 尺码表图片已复制到: %s' % dest)
                        _b64 = base64.b64encode(dest.encode('utf-8')).decode('ascii')
                        web.page().runJavaScript(
                            "window.__onRSCPickSizeImage && window.__onRSCPickSizeImage('" + _b64 + "');"
                        )
                except Exception as e:
                    _write_diag_file('[设置中心] 尺码表选图失败: %r' % e)
            elif method == 'save_product_reply' and isinstance(arg, dict):
                # 保存商品个性回复：写库后把最新列表回传给页面刷新主表格
                bridge.save_product_reply(json.dumps(arg, ensure_ascii=False))
                try:
                    _b64 = base64.b64encode(bridge.get_product_replies().encode('utf-8')).decode('ascii')
                    web.page().runJavaScript(
                        "window.__onRSCProductReplies && window.__onRSCProductReplies(decodeURIComponent(escape(atob('" + _b64 + "'))));"
                    )
                except Exception:
                    pass
            elif method == 'get_product_replies':
                # 页面请求商品个性回复最新列表（base64 回传）
                try:
                    _b64 = base64.b64encode(bridge.get_product_replies().encode('utf-8')).decode('ascii')
                    web.page().runJavaScript(
                        "window.__onRSCProductReplies && window.__onRSCProductReplies(decodeURIComponent(escape(atob('" + _b64 + "'))));"
                    )
                except Exception:
                    pass
            elif method == 'delete_product_reply' and isinstance(arg, dict):
                # 删除商品个性回复：删库后把最新列表回传给页面刷新主表格
                try:
                    bridge.delete_product_reply(int(arg.get('id', 0)))
                except Exception:
                    pass
                try:
                    _b64 = base64.b64encode(bridge.get_product_replies().encode('utf-8')).decode('ascii')
                    web.page().runJavaScript(
                        "window.__onRSCProductReplies && window.__onRSCProductReplies(decodeURIComponent(escape(atob('" + _b64 + "'))));"
                    )
                except Exception:
                    pass
            elif method == 'set_product_direct' and isinstance(arg, dict):
                # 切换某条商品个性回复的「直接回复」开关
                try:
                    bridge.set_product_direct(int(arg.get('id', 0)), int(arg.get('direct', 1)))
                except Exception:
                    pass
            elif method == 'set_general_direct' and isinstance(arg, dict):
                # 切换某条通用回复的「直接回复」开关
                bridge.set_general_direct(json.dumps(arg, ensure_ascii=False))
            elif method == 'export_config':
                # 一键导出配置：文件框 + 打包由桥处理，把结果回传给页面浮条提示
                try:
                    _res = bridge.export_config()
                    web.page().runJavaScript(
                        "window.__onRSCConfigResult && window.__onRSCConfigResult(" + json.dumps(_res) + ");")
                except Exception:
                    pass
            elif method == 'import_config':
                # 一键导入配置：导入成功后重载页面让新数据立即生效，再弹结果提示
                try:
                    _res = bridge.import_config()
                    try:
                        _ok = bool(json.loads(_res or '{}').get('ok', False))
                    except Exception:
                        _ok = False
                    if _ok:
                        _load_page()
                        from PyQt6.QtCore import QTimer
                        QTimer.singleShot(1200, lambda: web.page().runJavaScript(
                            "window.__onRSCConfigResult && window.__onRSCConfigResult(" + json.dumps(_res) + ");"))
                    else:
                        web.page().runJavaScript(
                            "window.__onRSCConfigResult && window.__onRSCConfigResult(" + json.dumps(_res) + ");")
                except Exception:
                    pass
            elif method == 'close':
                # 关窗前先让输入法"有序搬家"：1) 收尾正在输入的内容；2) 焦点先交还主界面
                # （此时新旧窗口都完好），输入法随焦点平稳切换；然后再关窗。
                # 此前卡死/崩溃正是发生在"旧窗半死、新窗未接手"的中间状态下输入法被系统调用
                try:
                    _im = QGuiApplication.inputMethod()
                    _im.commit()
                    _im.reset()
                except Exception:
                    pass
                try:
                    self.setFocus()
                    self.activateWindow()
                except Exception:
                    pass
                dlg.close()
                _write_diag_file('[设置中心] 关窗完成')
                # 窗口完全关闭后再把主窗口顶回前台（否则前台身份会被其他程序窗口抢走）
                QTimer.singleShot(0, self._raise_main_window)
            elif method == 'get_products':
                # 页面请求商品知识库最新数据：把 JSON 用 base64 塞回给页面（实时刷新绑定商品列表）
                try:
                    _b64 = base64.b64encode(bridge.get_products().encode('utf-8')).decode('ascii')
                    web.page().runJavaScript(
                        "window.__onRSCProducts && window.__onRSCProducts(decodeURIComponent(escape(atob('" + _b64 + "'))));"
                    )
                except Exception:
                    pass
            elif method == 'get_general_replies':
                # 页面请求多份规则（刷新页面后恢复数据用）
                try:
                    _b64 = base64.b64encode(bridge.get_general_replies().encode('utf-8')).decode('ascii')
                    web.page().runJavaScript(
                        "window.__onRSCGeneralReply && window.__onRSCGeneralReply(decodeURIComponent(escape(atob('" + _b64 + "'))));"
                    )
                except Exception:
                    pass
            elif method in ('get_all_settings', 'get_model_options'):
                # 页面刷新后一次性回填设置+模型+PRO状态，避免页面停留在演示数据
                try:
                    _models = json.loads(bridge.get_model_options())
                    _opt = {
                        'settings': json.loads(bridge.get_all_settings()),
                        'models': _models.get('models', []),
                        'pro_unlocked': _models.get('pro_unlocked', False),
                        'free_model': _models.get('free_model', ''),
                    }
                    _b64 = base64.b64encode(json.dumps(_opt, ensure_ascii=False).encode('utf-8')).decode('ascii')
                    web.page().runJavaScript(
                        "window.__onRSCOptions && window.__onRSCOptions(decodeURIComponent(escape(atob('" + _b64 + "'))));"
                    )
                except Exception:
                    pass
            elif method == 'get_missed':
                # 页面请求待补充未答问题：后台线程读库，读完推给页面刷新（不卡界面）
                _fetch_missed_bg()
            elif method == 'save_missed_reply' and isinstance(arg, dict):
                # 补充未答问题：写规则后把最新列表回传给页面刷新
                bridge.save_missed_reply(json.dumps(arg, ensure_ascii=False))
                _fetch_missed_bg()
                # 补充可能改动了通用规则，同步回传最新通用规则给页面刷新
                try:
                    _b64 = base64.b64encode(bridge.get_general_replies().encode('utf-8')).decode('ascii')
                    web.page().runJavaScript(
                        "window.__onRSCGeneralReply && window.__onRSCGeneralReply(decodeURIComponent(escape(atob('" + _b64 + "'))));"
                    )
                except Exception:
                    pass
                # 补充商品指向问题会新增商品个性回复，同步回传最新商品个性回复给页面刷新
                try:
                    _b64 = base64.b64encode(bridge.get_product_replies().encode('utf-8')).decode('ascii')
                    web.page().runJavaScript(
                        "window.__onRSCProductReplies && window.__onRSCProductReplies(decodeURIComponent(escape(atob('" + _b64 + "'))));"
                    )
                except Exception:
                    pass
            elif method == 'hide_missed' and isinstance(arg, dict):
                # 永久隐藏一组未答问题：标记后把最新列表回传给页面刷新
                bridge.hide_missed(json.dumps(arg, ensure_ascii=False))
                _fetch_missed_bg()
            elif method == 'get_size_charts':
                # 页面请求已添加尺码表列表（base64 回传刷新卡片列表）
                try:
                    _b64 = base64.b64encode(bridge.get_size_charts().encode('utf-8')).decode('ascii')
                    web.page().runJavaScript(
                        "window.__onRSCSizeCharts && window.__onRSCSizeCharts(decodeURIComponent(escape(atob('" + _b64 + "'))));"
                    )
                except Exception:
                    pass
            elif method == 'save_size_chart' and isinstance(arg, dict):
                # 保存尺码表：写库后把结果回传页面（'ok' = 成功，其他 = 失败原因）
                try:
                    _res = bridge.save_size_chart(json.dumps(arg, ensure_ascii=False))
                    _esc = _res.replace('\\', '\\\\').replace("'", "\\'")
                    web.page().runJavaScript("window.__onRSCSizeChartResult && window.__onRSCSizeChartResult('" + _esc + "');")
                except Exception:
                    pass
            elif method == 'delete_size_chart' and isinstance(arg, dict):
                # 删除尺码表：删库后把结果回传页面（'ok' = 成功，其他 = 失败原因）
                try:
                    _res = bridge.delete_size_chart(int(arg.get('id') or 0))
                    _esc = _res.replace('\\', '\\\\').replace("'", "\\'")
                    web.page().runJavaScript("window.__onRSCSizeChartResult && window.__onRSCSizeChartResult('" + _esc + "');")
                except Exception:
                    pass
            elif method == 'get_exclude_props':
                # 页面请求排除属性清单（base64 回传）
                try:
                    _b64 = base64.b64encode(bridge.get_exclude_props().encode('utf-8')).decode('ascii')
                    web.page().runJavaScript(
                        "window.__onRSCExcludeProps && window.__onRSCExcludeProps(decodeURIComponent(escape(atob('" + _b64 + "'))));"
                    )
                except Exception:
                    pass
            elif method == 'get_prop_options':
                # 页面请求商品知识库全部属性名清单（base64 回传）
                try:
                    _b64 = base64.b64encode(bridge.get_prop_options().encode('utf-8')).decode('ascii')
                    web.page().runJavaScript(
                        "window.__onRSCPropOptions && window.__onRSCPropOptions(decodeURIComponent(escape(atob('" + _b64 + "'))));"
                    )
                except Exception:
                    pass
            elif method == 'save_exclude_props' and isinstance(arg, dict):
                # 保存排除属性清单：写配置后回传结果（'ok' = 成功，其他 = 失败原因）
                try:
                    _res = bridge.save_exclude_props(json.dumps(arg, ensure_ascii=False))
                    _esc = _res.replace('\\', '\\\\').replace("'", "\\'")
                    web.page().runJavaScript("window.__onRSCExcludePropsResult && window.__onRSCExcludePropsResult('" + _esc + "');")
                except Exception:
                    pass
            elif method == 'get_product_attrs':
                # 页面请求商品知识库完整列表（base64 回传）
                try:
                    _b64 = base64.b64encode(bridge.get_product_attrs().encode('utf-8')).decode('ascii')
                    web.page().runJavaScript(
                        "window.__onRSCProductAttrs && window.__onRSCProductAttrs(decodeURIComponent(escape(atob('" + _b64 + "'))));"
                    )
                except Exception:
                    pass
            elif method == 'learn_products':
                # 设置中心"一键学习商品详情内容"：扫描并整理销量达标商品（后台异步，进度实时回传）
                try:
                    _started = bridge.start_learn_products()
                    _s = str(_started or '')
                    if _s.startswith('started'):
                        _learn_n = 0
                        try:
                            _learn_n = int(_s.split(':', 1)[1])
                        except Exception:
                            _learn_n = 0
                        web.page().runJavaScript("window.__onRSCLearnStarted && window.__onRSCLearnStarted(" + str(_learn_n) + ");")
                    else:
                        _esc = str(_s or '学习启动失败').replace('\\', '\\\\').replace("'", "\\'")
                        web.page().runJavaScript("window.__onRSCLearnStarted && window.__onRSCLearnStarted(0);")
                        web.page().runJavaScript("window.__onRSCLearnProgress && window.__onRSCLearnProgress('{\"error\":\"" + _esc + "\",\"finished\":true,\"total\":0,\"done\":0,\"ok\":0,\"fail\":0}');")
                except Exception:
                    pass
            elif method == 'learn_status':
                # 设置中心读取最近一批"一键学习"的进度（退出设置中心重进后恢复显示进度/结果）
                try:
                    _esc2 = str(bridge.get_learn_status()).replace('\\', '\\\\').replace("'", "\\'")
                    web.page().runJavaScript("window.__onRSCLearnStatus && window.__onRSCLearnStatus('" + _esc2 + "');")
                except Exception:
                    pass
            elif method == 'update_product_attr' and isinstance(arg, dict):
                # 保存某条商品知识内容：写库后回传结果
                try:
                    _res = bridge.update_product_attr(json.dumps(arg, ensure_ascii=False))
                    _esc = _res.replace('\\', '\\\\').replace("'", "\\'")
                    web.page().runJavaScript("window.__onRSCProductAttrResult && window.__onRSCProductAttrResult('" + _esc + "');")
                except Exception:
                    pass
            elif method == 'batch_append_description' and isinstance(arg, dict):
                # 批量追加描述：写库后回传结果
                try:
                    _res = bridge.batch_append_description(json.dumps(arg, ensure_ascii=False))
                    _esc = _res.replace('\\', '\\\\').replace("'", "\\'")
                    web.page().runJavaScript("window.__onRSCBatchAppendResult && window.__onRSCBatchAppendResult('" + _esc + "');")
                except Exception:
                    pass
            # 恢复标题，防止同一个指令被重复处理
            try:
                web.page().runJavaScript("document.title = '设置中心';")
            except Exception:
                pass
        self._rsc_web = web
        # 页面现在是启动时预建、多次打开复用的同一份：信号改挂在"本次的网页控件"上
        # （控件每次都是新的，不会随复用次数累积连接；若挂在页面上会一层层叠加）
        web.titleChanged.connect(_on_title_changed)

        # 拦截非内置协议 + 外部链接点击（防止系统弹外部应用）
        # （kuaai 是设置中心的内部协议：本地目录映射，必须在白名单里）
        # 页面是复用的同一份：导航拦截只挂一次（靠页面上的标记位），避免层层包裹
        if not getattr(web.page(), '_rsc_nav_hooked', False):
            old_accept = web.page().acceptNavigationRequest
            SAFE_SCHEMES = {'http', 'https', 'file', 'about', 'data', 'blob', 'kuaai', ''}
            def _accept(url, typ, isMain):
                url_str = url.toString()
                scheme = url.scheme().lower()
                if scheme not in SAFE_SCHEMES:
                    return False
                if typ == QWebEnginePage.NavigationTypeLinkClicked:
                    return False
                return old_accept(url, typ, isMain)
            web.page().acceptNavigationRequest = _accept
            web.page()._rsc_nav_hooked = True

        # #app-close 哈希 → 关闭窗口（兜底）
        def _on_url_changed(url):
            if url.fragment() == 'app-close':
                try:
                    _im = QGuiApplication.inputMethod()
                    _im.commit()
                    _im.reset()
                except Exception:
                    pass
                try:
                    self.setFocus()
                    self.activateWindow()
                except Exception:
                    pass
                dlg.close()
                QTimer.singleShot(0, self._raise_main_window)
        web.urlChanged.connect(_on_url_changed)
