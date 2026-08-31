from fire_browser.main_window._deps import *
import os


class _MsgCenter:
    # 主窗口零件：@msgcenter（开源演示版）
    # 原模块含消息处理相关业务，已全部移除。这里仅保留主窗口按钮调用的方法占位。

    def _load_filter_keywords(self):
        """开源演示版：回复策略功能未接入，返回空列表"""
        return []

    def _open_blacklist(self):
        """开源演示版：回复策略（黑名单/低优先级）功能未接入"""
        try:
            msg_warn(self, "提示", "开源演示版：黑名单/回复策略功能未接入")
        except Exception:
            pass

    def _load_msg_center(self):
        """从文件读取历史记录（仅本地展示数据，不含业务处理）"""
        f = getattr(self, '_msg_center_file', '')
        try:
            if f and os.path.exists(f):
                with open(f, 'r', encoding='utf-8') as fp:
                    data = json.load(fp)
                return data if isinstance(data, list) else []
        except Exception:
            pass
        return []

    def _save_msg_center(self):
        """写入历史记录到文件"""
        f = getattr(self, '_msg_center_file', '')
        try:
            if f:
                os.makedirs(os.path.dirname(f), exist_ok=True)
                with open(f, 'w', encoding='utf-8') as fp:
                    json.dump(self._blocked_transfer_list, fp, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _sync_notices(self):
        """开源演示版：公告推送未接入，空实现（兼容心跳定时器调用）"""
        return

    def _show_msg_center(self):
        """开源演示版：消息中心未接入，提示占位"""
        try:
            msg_warn(self, "提示", "开源演示版：消息中心功能未接入")
        except Exception:
            pass