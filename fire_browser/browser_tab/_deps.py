# 快应AI - fire_browser.browser_tab 的依赖聚合模块
# 把 BrowserTab 各部分(零件)用到的所有外部名字集中在这里；每个零件文件统一 `from ._deps import *`。
# 这样比每个零件各自列一长串 import 更不易漏。只放"名字"不写业务逻辑。

import sys, os, json, re, time, traceback, hashlib, subprocess, tempfile, shutil, zipfile, threading, functools, ctypes, io
import threading as _threading
import urllib.request, urllib.error
import database
from datetime import datetime, date, timedelta

# Qt 全套(与主窗口相同用整包导入，保证任何 Qt 类都能取到)
from PyQt6.QtWidgets import (
    QWidget, QApplication, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QTextEdit, QLineEdit, QComboBox, QFileDialog, QMessageBox, QInputDialog, QMenu,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QScrollArea, QFrame,
    QDialog, QSystemTrayIcon, QCheckBox, QRadioButton, QProgressDialog, QSizePolicy,
    QToolTip, QListWidget, QListWidgetItem, QSplitter, QStackedWidget, QTextBrowser,
    QButtonGroup, QGraphicsDropShadowEffect,
)
from PyQt6.QtGui import (
    QIcon, QFont, QColor, QPainter, QPen, QBrush, QPixmap, QImage,
    QTextCursor, QTextCharFormat, QTextOption, QAction, QKeySequence, QPalette,
    QRegion, QBitmap, QCursor, QTransform, QGuiApplication,
)
from PyQt6.QtCore import (
    Qt, QTimer, QObject, pyqtSignal, pyqtSlot, QThread, QMetaObject, Q_ARG, Q_RETURN_ARG,
    QUrl, QPoint, QPointF, QRect, QRectF, QSize, QEvent, QSettings, QStandardPaths,
    QDateTime, QDate, QTime, QProcess, QBuffer, QIODevice, QFile, QDir, QLocale,
    QByteArray, QAbstractNativeEventFilter, QModelIndex,
    QTimerEvent, QObjectCleanupHandler, QEasingCurve, QVariantAnimation,
)
from PyQt6.QtWebEngineCore import (
    QWebEngineProfile, QWebEnginePage, QWebEngineScript, QWebEngineSettings,
)

# 网页内核统一走 Qt 内置浏览器（QtWebEngine）兼容层(与主窗口一致)
from qt_web_compat import (
    QtView as QWebEngineView,
    QtProfile as QWebEngineProfile,
    QtPage as QWebEnginePage,
    QtScript as QWebEngineScript,
)

from js_inject import INJECT_SCRIPT
from log_manager import LogManager, dated_log_path
from nickname_manager import NicknameManager
from updater import Updater
from ui_widgets import (
    CustomButton as _CustomButton,
    SoftButton as _SoftButton,
    mk_primary_btn as _mk_primary_btn,
    mk_secondary_btn as _mk_secondary_btn,
    mk_danger_btn as _mk_danger_btn,
    OverlayContainer,
    ShopTabBar,
    ShopTextButton,
    WinButton,
    SideBarButton,
    StatusDotLabel,
    FONT_FAMILY,
    msg_warn,
)
from message_modules import ReplyEngine, MessageSender
from message_scheduler import Scheduler
from ai_service import AIService
from config_manager import ConfigManager, DEFAULT_TRANSFER_TEXT
from shop_manager import ShopManager

# 本项目自拆的工具/零件(路径、UI小件、AI线程)
from fire_browser.pathutils import (
    LOCAL_VERSION, _cosine, _si_pid_is_python, _data_dir, _log_dir, _pic_dir,
    _resolve_pic_file, _remap_pic_path, _remap_gk_image_paths,
    _write_diag_file, _write_life, _write_exit_flag, _native_window_rect,
    _apply_win11_rounded,
)
from fire_browser.widgets import (
    SCROLLBAR_STYLE, MsgCard, _LoadingSpinner, LoadingMask,
    _attach_loading_mask, _js_cb_safe,
)
from fire_browser.workers import (
    任务A, 任务B, 任务C, 任务D, 任务E, 任务F,
)
from fire_browser.settings_bridge import ReplySettingsBridge

_DEBUG_MODE = '--debug' in sys.argv

# 项目根目录：本文件位于 <根>/fire_browser/browser_tab/_deps.py，上溯三级即根
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

__all__ = [n for n in globals() if not n.startswith('__')]