# 快应UI 开源版 - 数据模块精简版
# 原模块为核心业务数据层（已删除）。这里只保留"顶部店铺标签 / 店铺列表"所需的最小平滑持久化
# （路径助手 + 店铺表 CRUD），不含任何业务逻辑。
import os
import sqlite3


def user_data_dir():
    """用户数据根目录（与配置文件同一用户目录下），不存在则创建"""
    base = os.environ.get('APPDATA') or os.path.expanduser('~')
    d = os.path.join(base, '快应AI', 'data')
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def log_dir():
    """诊断日志目录（与用户数据目录一致）"""
    return user_data_dir()


DB_PATH = os.path.join(user_data_dir(), 'fire_browser.db')


def get_conn():
    """获取数据库连接"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    return conn


def init_database():
    """初始化数据库表结构（开源版只保留店铺信息表）"""
    conn = get_conn()
    try:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS shopInfo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT NOT NULL,
                shop_name TEXT NOT NULL,
                sub_account TEXT DEFAULT '',
                password TEXT DEFAULT '',
                cookie TEXT DEFAULT '',
                proxy_server TEXT DEFAULT '',
                proxy_port TEXT DEFAULT '',
                proxy_username TEXT DEFAULT '',
                proxy_password TEXT DEFAULT '',
                proxy_scheme TEXT DEFAULT '',
                open_url TEXT DEFAULT 'https://mms.pinduoduo.com/chat-merchant/#/',
                top_shop INTEGER DEFAULT 0,
                is_login INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
    finally:
        conn.close()


def get_all_shops():
    """获取所有店铺"""
    conn = get_conn()
    try:
        shops = conn.execute('SELECT * FROM shopInfo ORDER BY top_shop DESC, id ASC').fetchall()
        return [dict(s) for s in shops]
    finally:
        conn.close()


def add_shop(data: dict):
    """添加店铺"""
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute('''
            INSERT INTO shopInfo (user_name, shop_name, sub_account, password,
                                  proxy_server, proxy_port, proxy_username, proxy_password,
                                  proxy_scheme, open_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('user_name', ''),
            data.get('shop_name', ''),
            data.get('sub_account', ''),
            data.get('password', ''),
            data.get('proxy_server', ''),
            data.get('proxy_port', ''),
            data.get('proxy_username', ''),
            data.get('proxy_password', ''),
            data.get('proxy_scheme', ''),
            data.get('open_url', 'https://mms.pinduoduo.com/chat-merchant/#/')
        ))
        conn.commit()
        shop_id = c.lastrowid
        return shop_id
    finally:
        conn.close()


def update_shop(shop_id: int, data: dict):
    """更新店铺"""
    conn = get_conn()
    try:
        fields = []
        values = []
        for k, v in data.items():
            if k in ['user_name', 'shop_name', 'sub_account', 'password', 'cookie',
                      'proxy_server', 'proxy_port', 'proxy_username', 'proxy_password',
                      'proxy_scheme', 'open_url', 'top_shop', 'is_login']:
                fields.append(f'{k} = ?')
                values.append(v)
        if fields:
            values.append(shop_id)
            conn.execute(f'UPDATE shopInfo SET {", ".join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?', values)
            conn.commit()
    finally:
        conn.close()


def delete_shop(shop_id: int):
    """删除店铺"""
    conn = get_conn()
    try:
        conn.execute('DELETE FROM shopInfo WHERE id = ?', (shop_id,))
        conn.commit()
    finally:
        conn.close()


# ── 兼容旧代码调用的空操作（对应业务已删除，只占位防止启动报错）──
def _noop(*_a, **_k):
    return None


for _n in ('clean_old_msgs', 'missed_cleanup_stale_single', 'missed_vague_cleaned',
           'missed_get_open', 'missed_vague_mark_cleaned', 'missed_hide'):
    globals()[_n] = _noop