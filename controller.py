"""
远程控制系统 - 控制端
带PyQt5图形界面的控制端程序
支持查看在线主机、截图、视频流、批量执行命令、鼠标键盘控制、自定义命令等
"""
import sys
import socket
import threading
import json
import base64
import os
from datetime import datetime

try:
    from PyQt5 import QtWidgets, QtGui, QtCore
    from PyQt5.QtWidgets import *
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
except ImportError:
    print("错误: 需要安装PyQt5")
    print("请运行: pip install PyQt5")
    sys.exit(1)


class ControllerGUI(QMainWindow):
    # 定义信号
    update_host_list_signal = pyqtSignal(list)
    update_image_signal = pyqtSignal(bytes, str)
    update_log_signal = pyqtSignal(str)
    update_file_list_signal = pyqtSignal(str, list)  # 文件列表更新信号
    show_file_content_signal = pyqtSignal(str, str, str)  # 显示文件内容信号 (filepath, filename, content)
    reconnect_success_signal = pyqtSignal()  # 重连成功信号

    def __init__(self):
        super().__init__()
        self.server_ip = None
        self.server_port = 5000
        self.sock = None
        self.connected = False
        self.auto_reconnect = True  # 自动重连标志

        # 自定义命令列表
        self.custom_commands = self.load_custom_commands()

        # 主机名映射 (agent_id -> custom_name)
        self.host_name_mapping = self.load_host_name_mapping()

        # 当前主机列表
        self.current_hosts = []

        # 视频质量设置
        self.video_quality = 'medium'

        # 鼠标键盘控制模式
        self.remote_control_mode = False
        self.keyboard_control_mode = False

        # 视频流状态
        self.video_streaming = False
        self.current_video_target = None

        # 原始图像尺寸（用于坐标转换）
        self.original_image_width = 1920
        self.original_image_height = 1080

        self.init_ui()

        # 连接信号
        self.update_host_list_signal.connect(self.update_host_list)
        self.update_image_signal.connect(self.update_image)
        self.update_log_signal.connect(self.append_log)
        self.update_file_list_signal.connect(self.update_file_list)
        self.show_file_content_signal.connect(self.show_file_content)
        self.reconnect_success_signal.connect(self.on_reconnect_success)

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle('🖥️ 远程控制系统 v1.0 - 控制端')
        self.setGeometry(100, 100, 1600, 1000)

        # 设置窗口最小尺寸
        self.setMinimumSize(1200, 800)

        # 设置应用图标和样式
        self.setStyleSheet(self.get_stylesheet())

        # 设置窗口背景渐变
        palette = QPalette()
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor(236, 240, 241))
        gradient.setColorAt(1, QColor(255, 255, 255))
        palette.setBrush(QPalette.Window, QBrush(gradient))
        self.setPalette(palette)

        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # 左侧面板
        left_panel = self.create_left_panel()
        main_layout.addWidget(left_panel, 1)

        # 右侧面板
        right_panel = self.create_right_panel()
        main_layout.addWidget(right_panel, 3)

        # 状态栏
        self.statusBar().showMessage('🔴 未连接')
        self.statusBar().setStyleSheet("""
            QStatusBar {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #34495e, stop:1 #2c3e50);
                color: white;
                font-size: 13px;
                font-weight: bold;
                padding: 5px;
            }
        """)

    def create_left_panel(self):
        """创建左侧面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)

        # 连接设置组
        conn_group = QGroupBox("🌐 服务器连接")
        conn_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #3498db;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }
        """)
        conn_layout = QVBoxLayout()

        # 服务器IP输入
        ip_layout = QHBoxLayout()
        ip_label = QLabel("服务器IP:")
        ip_label.setStyleSheet("font-weight: bold;")
        ip_layout.addWidget(ip_label)
        self.ip_input = QLineEdit("127.0.0.1")
        self.ip_input.setPlaceholderText("输入服务器IP地址")
        self.ip_input.setToolTip("输入远程控制服务器的IP地址")
        ip_layout.addWidget(self.ip_input)
        conn_layout.addLayout(ip_layout)

        # 连接按钮
        self.connect_btn = QPushButton("🔌 连接服务器")
        self.connect_btn.setMinimumHeight(35)
        self.connect_btn.setToolTip("点击连接到远程控制服务器")
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
        """)
        self.connect_btn.clicked.connect(self.toggle_connection)
        conn_layout.addWidget(self.connect_btn)

        conn_group.setLayout(conn_layout)
        layout.addWidget(conn_group)

        # 主机列表组
        host_group = QGroupBox("💻 在线主机")
        host_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #2ecc71;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }
        """)
        host_layout = QVBoxLayout()

        # 主机列表
        self.host_list = QListWidget()
        self.host_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.host_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.host_list.customContextMenuRequested.connect(self.show_host_context_menu)
        self.host_list.itemClicked.connect(self.on_host_clicked)
        self.host_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                background-color: white;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #ecf0f1;
            }
            QListWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #ecf0f1;
            }
        """)
        host_layout.addWidget(self.host_list)

        # 按钮布局
        btn_layout = QHBoxLayout()

        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.setMinimumHeight(30)
        refresh_btn.setToolTip("刷新在线主机列表")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        refresh_btn.clicked.connect(self.refresh_hosts)
        btn_layout.addWidget(refresh_btn)

        # 全选按钮
        select_all_btn = QPushButton("☑️ 全选")
        select_all_btn.setMinimumHeight(30)
        select_all_btn.setToolTip("选择所有在线主机")
        select_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        select_all_btn.clicked.connect(self.select_all_hosts)
        btn_layout.addWidget(select_all_btn)

        host_layout.addLayout(btn_layout)

        host_group.setLayout(host_layout)
        layout.addWidget(host_group)

        # 文件管理器组
        file_group = QGroupBox("📁 文件管理")
        file_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #16a085;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }
        """)
        file_layout = QVBoxLayout()

        # 磁盘驱动器选择
        drive_layout = QHBoxLayout()
        drive_label = QLabel("💾 磁盘:")
        drive_label.setStyleSheet("font-weight: bold;")
        drive_layout.addWidget(drive_label)

        self.drive_combo = QComboBox()
        self.drive_combo.setMinimumHeight(25)
        self.drive_combo.setPlaceholderText("选择磁盘...")
        self.drive_combo.setStyleSheet("""
            QComboBox {
                border: 2px solid #bdc3c7;
                border-radius: 5px;
                padding: 5px;
                background-color: white;
            }
            QComboBox:hover {
                border: 2px solid #16a085;
            }
            QComboBox::drop-down {
                border: none;
            }
        """)
        self.drive_combo.currentIndexChanged.connect(self.on_drive_selected)
        drive_layout.addWidget(self.drive_combo)

        refresh_drives_btn = QPushButton("🔄 刷新磁盘")
        refresh_drives_btn.setMinimumHeight(25)
        refresh_drives_btn.setToolTip("刷新磁盘列表")
        refresh_drives_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        refresh_drives_btn.clicked.connect(self.refresh_drives)
        drive_layout.addWidget(refresh_drives_btn)
        file_layout.addLayout(drive_layout)

        # 当前路径显示
        path_layout = QHBoxLayout()
        path_label = QLabel("📂 路径:")
        path_label.setStyleSheet("font-weight: bold;")
        path_layout.addWidget(path_label)

        self.current_path_input = QLineEdit()
        self.current_path_input.setPlaceholderText("输入路径或从磁盘选择...")
        self.current_path_input.setStyleSheet("""
            QLineEdit {
                border: 2px solid #bdc3c7;
                border-radius: 5px;
                padding: 5px;
                background-color: white;
            }
        """)
        path_layout.addWidget(self.current_path_input)

        browse_btn = QPushButton("🔍 浏览")
        browse_btn.setMinimumHeight(25)
        browse_btn.setToolTip("浏览指定路径")
        browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #16a085;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #138d75;
            }
        """)
        browse_btn.clicked.connect(self.browse_remote_files)
        path_layout.addWidget(browse_btn)
        file_layout.addLayout(path_layout)

        # 文件列表
        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(150)
        self.file_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self.show_file_context_menu)
        self.file_list.itemDoubleClicked.connect(self.on_file_double_click)
        self.file_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                background-color: white;
                font-size: 11px;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #ecf0f1;
            }
            QListWidget::item:selected {
                background-color: #16a085;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #ecf0f1;
            }
        """)
        file_layout.addWidget(self.file_list)

        file_group.setLayout(file_layout)
        layout.addWidget(file_group)

        # 控制按钮组
        control_group = QGroupBox("🎮 控制操作")
        control_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #e74c3c;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }
        """)
        control_layout = QVBoxLayout()

        # 截图按钮
        screenshot_btn = QPushButton("📷 截图")
        screenshot_btn.setMinimumHeight(35)
        screenshot_btn.setToolTip("获取选中主机的屏幕截图")
        screenshot_btn.setStyleSheet("""
            QPushButton {
                background-color: #9b59b6;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #8e44ad;
            }
            QPushButton:pressed {
                background-color: #7d3c98;
            }
        """)
        screenshot_btn.clicked.connect(self.send_screenshot)
        control_layout.addWidget(screenshot_btn)

        # 视频流按钮
        video_layout = QHBoxLayout()
        self.start_video_btn = QPushButton("▶ 开始视频")
        self.start_video_btn.setMinimumHeight(35)
        self.start_video_btn.setToolTip("开始实时视频流监控")
        self.start_video_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:pressed {
                background-color: #1e8449;
            }
        """)
        self.start_video_btn.clicked.connect(self.start_video)
        video_layout.addWidget(self.start_video_btn)

        self.stop_video_btn = QPushButton("⏹ 停止视频")
        self.stop_video_btn.setMinimumHeight(35)
        self.stop_video_btn.setToolTip("停止视频流")
        self.stop_video_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:pressed {
                background-color: #a93226;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        self.stop_video_btn.clicked.connect(self.stop_video)
        self.stop_video_btn.setEnabled(False)
        video_layout.addWidget(self.stop_video_btn)
        control_layout.addLayout(video_layout)

        # 视频质量选择
        quality_layout = QHBoxLayout()
        quality_label = QLabel("📊 视频质量:")
        quality_label.setStyleSheet("font-weight: bold;")
        quality_layout.addWidget(quality_label)
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(['低 (640x480)', '中 (800x600)', '高 (1280x720)', '超高 (1920x1080 90%无损)'])
        self.quality_combo.setCurrentIndex(1)
        self.quality_combo.setToolTip("选择视频质量：低质量适合网络较差时使用，超高质量为90%无损画质")
        self.quality_combo.setStyleSheet("""
            QComboBox {
                border: 2px solid #bdc3c7;
                border-radius: 5px;
                padding: 6px;
                background-color: white;
                font-size: 13px;
            }
            QComboBox:hover {
                border: 2px solid #3498db;
            }
        """)
        self.quality_combo.currentIndexChanged.connect(self.on_quality_changed)
        quality_layout.addWidget(self.quality_combo)
        control_layout.addLayout(quality_layout)

        # 远程控制按钮（鼠标和键盘）
        remote_control_layout = QHBoxLayout()

        self.remote_control_btn = QPushButton("🖱 鼠标控制")
        self.remote_control_btn.setCheckable(True)
        self.remote_control_btn.setMinimumHeight(35)
        self.remote_control_btn.setToolTip("启用/禁用远程鼠标控制")
        self.remote_control_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
            QPushButton:checked {
                background-color: #f39c12;
                border: 3px solid #e67e22;
                font-weight: bold;
            }
            QPushButton:checked:hover {
                background-color: #e67e22;
            }
        """)
        self.remote_control_btn.clicked.connect(self.toggle_remote_control)
        remote_control_layout.addWidget(self.remote_control_btn)

        # 键盘控制按钮
        self.keyboard_control_btn = QPushButton("⌨️ 键盘控制")
        self.keyboard_control_btn.setCheckable(True)
        self.keyboard_control_btn.setMinimumHeight(35)
        self.keyboard_control_btn.setToolTip("启用/禁用远程键盘控制")
        self.keyboard_control_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
            QPushButton:checked {
                background-color: #9b59b6;
                border: 3px solid #8e44ad;
                font-weight: bold;
            }
            QPushButton:checked:hover {
                background-color: #8e44ad;
            }
        """)
        self.keyboard_control_btn.clicked.connect(self.toggle_keyboard_control)
        remote_control_layout.addWidget(self.keyboard_control_btn)

        control_layout.addLayout(remote_control_layout)

        control_group.setLayout(control_layout)
        layout.addWidget(control_group)

        layout.addStretch()

        return panel

    def create_right_panel(self):
        """创建右侧面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)

        # 图像显示区
        image_group = QGroupBox("🖥️ 屏幕显示")
        image_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #34495e;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }
        """)
        image_layout = QVBoxLayout()

        # 当前显示的主机
        self.current_host_label = QLabel("📍 当前显示: 无")
        self.current_host_label.setStyleSheet("""
            QLabel {
                background-color: #ecf0f1;
                padding: 8px;
                border-radius: 5px;
                font-weight: bold;
                color: #2c3e50;
            }
        """)
        image_layout.addWidget(self.current_host_label)

        # 图像标签
        self.image_label = QLabel()
        self.image_label.setMinimumSize(800, 600)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("""
            QLabel {
                background-color: #2c3e50;
                color: #95a5a6;
                border: 2px solid #34495e;
                border-radius: 5px;
                font-size: 14px;
            }
        """)
        self.image_label.setText("⏳ 等待图像...\n\n点击左侧主机，然后点击截图或开始视频")
        self.image_label.setScaledContents(False)

        # 添加鼠标事件
        self.image_label.mousePressEvent = self.on_image_mouse_press
        self.image_label.mouseMoveEvent = self.on_image_mouse_move
        self.image_label.wheelEvent = self.on_image_wheel

        # 添加滚动区域
        scroll = QScrollArea()
        scroll.setWidget(self.image_label)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #2c3e50;
            }
        """)
        image_layout.addWidget(scroll)

        image_group.setLayout(image_layout)
        layout.addWidget(image_group, 3)

        # 命令执行区
        cmd_group = QGroupBox("⚡ 命令执行")
        cmd_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #f39c12;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }
        """)
        cmd_layout = QVBoxLayout()

        # 自定义命令下拉框
        cmd_select_layout = QHBoxLayout()
        cmd_label = QLabel("⚡ 快捷命令:")
        cmd_label.setStyleSheet("font-weight: bold;")
        cmd_select_layout.addWidget(cmd_label)
        self.cmd_combo = QComboBox()
        self.cmd_combo.addItem("-- 选择命令 --")
        for cmd_name in self.custom_commands.keys():
            self.cmd_combo.addItem(cmd_name)
        self.cmd_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #bdc3c7;
                border-radius: 3px;
                padding: 5px;
                background-color: white;
            }
            QComboBox:hover {
                border: 1px solid #f39c12;
            }
        """)
        self.cmd_combo.currentTextChanged.connect(self.on_cmd_selected)
        cmd_select_layout.addWidget(self.cmd_combo)

        manage_cmd_btn = QPushButton("⚙️ 管理")
        manage_cmd_btn.setMinimumHeight(30)
        manage_cmd_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        manage_cmd_btn.clicked.connect(self.manage_commands)
        cmd_select_layout.addWidget(manage_cmd_btn)
        cmd_layout.addLayout(cmd_select_layout)

        # 命令输入
        cmd_input_layout = QHBoxLayout()
        cmd_input_label = QLabel("💻 命令:")
        cmd_input_label.setStyleSheet("font-weight: bold;")
        cmd_input_layout.addWidget(cmd_input_label)
        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText("输入命令或脚本路径 (如: ipconfig 或 C:\\script.bat)")
        self.cmd_input.setStyleSheet("""
            QLineEdit {
                border: 2px solid #bdc3c7;
                border-radius: 5px;
                padding: 8px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 2px solid #3498db;
            }
        """)
        self.cmd_input.returnPressed.connect(self.send_command)
        cmd_input_layout.addWidget(self.cmd_input)
        cmd_layout.addLayout(cmd_input_layout)

        # 执行按钮和管理员权限选项
        exec_layout = QHBoxLayout()
        self.admin_checkbox = QCheckBox("🔐 管理员权限")
        self.admin_checkbox.setStyleSheet("""
            QCheckBox {
                font-weight: bold;
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
        """)
        exec_layout.addWidget(self.admin_checkbox)

        send_cmd_btn = QPushButton("▶️ 执行命令")
        send_cmd_btn.setMinimumHeight(35)
        send_cmd_btn.setStyleSheet("""
            QPushButton {
                background-color: #e67e22;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #d35400;
            }
        """)
        send_cmd_btn.clicked.connect(self.send_command)
        exec_layout.addWidget(send_cmd_btn)
        cmd_layout.addLayout(exec_layout)

        # 日志输出
        log_label = QLabel("📋 执行日志:")
        log_label.setStyleSheet("font-weight: bold; margin-top: 5px;")
        cmd_layout.addWidget(log_label)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(200)
        self.log_output.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: Consolas, monospace;
                font-size: 11px;
                border: 2px solid #34495e;
                border-radius: 5px;
                padding: 5px;
            }
        """)
        cmd_layout.addWidget(self.log_output)

        # 清空日志按钮
        clear_log_btn = QPushButton("🗑️ 清空日志")
        clear_log_btn.setMinimumHeight(30)
        clear_log_btn.setStyleSheet("""
            QPushButton {
                background-color: #7f8c8d;
                color: white;
                border: none;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #95a5a6;
            }
        """)
        clear_log_btn.clicked.connect(self.log_output.clear)
        cmd_layout.addWidget(clear_log_btn)

        cmd_group.setLayout(cmd_layout)
        layout.addWidget(cmd_group, 1)

        return panel

    def get_stylesheet(self):
        """获取全局样式表 - 增强版"""
        return """
            QMainWindow {
                background-color: #ecf0f1;
            }

            /* 通用按钮样式 */
            QPushButton {
                min-height: 30px;
                border-radius: 5px;
                padding: 6px 12px;
                font-size: 13px;
                font-weight: 500;
                transition: all 0.3s ease;
            }
            QPushButton:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            }
            QPushButton:pressed {
                transform: translateY(0px);
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }

            /* 输入框样式 */
            QLineEdit {
                border: 2px solid #bdc3c7;
                border-radius: 5px;
                padding: 8px;
                background-color: white;
                font-size: 13px;
                selection-background-color: #3498db;
            }
            QLineEdit:focus {
                border: 2px solid #3498db;
                background-color: #f8f9fa;
            }
            QLineEdit:hover {
                border: 2px solid #95a5a6;
            }

            /* 文本编辑框样式 */
            QTextEdit {
                border: 2px solid #34495e;
                border-radius: 5px;
                padding: 8px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
            }

            /* 下拉框样式 */
            QComboBox {
                border: 2px solid #bdc3c7;
                border-radius: 5px;
                padding: 6px;
                background-color: white;
                font-size: 13px;
            }
            QComboBox:hover {
                border: 2px solid #3498db;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #34495e;
                margin-right: 5px;
            }

            /* 复选框样式 */
            QCheckBox {
                font-size: 13px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #bdc3c7;
                border-radius: 3px;
                background-color: white;
            }
            QCheckBox::indicator:hover {
                border: 2px solid #3498db;
            }
            QCheckBox::indicator:checked {
                background-color: #3498db;
                border: 2px solid #2980b9;
                image: none;
            }

            /* 标签样式 */
            QLabel {
                font-size: 13px;
                color: #2c3e50;
            }

            /* 滚动条样式 */
            QScrollBar:vertical {
                border: none;
                background: #ecf0f1;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #95a5a6;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #7f8c8d;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }

            /* 工具提示样式 */
            QToolTip {
                background-color: #34495e;
                color: white;
                border: 1px solid #2c3e50;
                border-radius: 4px;
                padding: 5px;
                font-size: 12px;
            }
        """

    def toggle_connection(self):
        """切换连接状态"""
        if not self.connected:
            self.connect_to_server()
        else:
            self.disconnect_from_server(user_initiated=True)

    def connect_to_server(self):
        """连接到服务器"""
        self.server_ip = self.ip_input.text().strip()

        if not self.server_ip:
            QMessageBox.warning(self, "错误", "请输入服务器IP地址")
            return

        self.append_log(f"正在连接到 {self.server_ip}:{self.server_port}...")

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # 设置socket超时
            self.sock.settimeout(30)  # 30秒超时
            self.sock.connect((self.server_ip, self.server_port))

            # 发送注册信息
            self.send_json({'type': 'controller', 'action': 'register'})

            self.connected = True
            self.auto_reconnect = True
            self.connect_btn.setText("🔌 断开连接")
            self.connect_btn.setStyleSheet("""
                QPushButton {
                    background-color: #e74c3c;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    font-weight: bold;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #c0392b;
                }
            """)
            self.ip_input.setEnabled(False)
            self.statusBar().showMessage(f'🟢 已连接到 {self.server_ip}:{self.server_port}')

            self.append_log("✅ 连接成功!")

            # 启动接收线程
            threading.Thread(target=self.receive_loop, daemon=True).start()

            # 刷新主机列表
            self.refresh_hosts()

        except Exception as e:
            QMessageBox.critical(self, "连接错误", f"无法连接到服务器:\n{str(e)}")
            self.append_log(f"❌ 连接失败: {e}")

    def disconnect_from_server(self, user_initiated=False):
        """断开服务器连接

        Args:
            user_initiated: 是否为用户主动断开（True则不自动重连）
        """
        if user_initiated:
            self.auto_reconnect = False

        self.connected = False
        if self.sock:
            try:
                self.sock.close()
            except:
                pass

        # 重置视频流状态
        self.video_streaming = False
        self.current_video_target = None
        self.start_video_btn.setEnabled(True)
        self.stop_video_btn.setEnabled(False)

        # 清除图像显示
        self.image_label.clear()
        self.image_label.setText("📺 等待视频流或截图...\n\n请先连接服务器")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.current_host_label.setText("📍 当前显示: 无")

        self.connect_btn.setText("🔌 连接服务器")
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        self.ip_input.setEnabled(True)
        self.statusBar().showMessage('🔴 未连接')
        self.host_list.clear()

        if user_initiated:
            self.update_log_signal.emit("✅ 已断开连接")
        else:
            self.update_log_signal.emit("⚠️ 连接已断开")

            # 如果启用自动重连，尝试重连
            if self.auto_reconnect and self.server_ip:
                self.update_log_signal.emit("🔄 5秒后尝试重新连接...")
                threading.Timer(5.0, self.try_reconnect).start()

    def try_reconnect(self):
        """尝试重新连接 - 使用信号避免线程安全问题"""
        if not self.auto_reconnect or self.connected:
            return

        try:
            self.update_log_signal.emit(f"🔄 正在重新连接到 {self.server_ip}:{self.server_port}...")

            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(30)
            self.sock.connect((self.server_ip, self.server_port))

            # 发送注册信息
            self.send_json({'type': 'controller', 'action': 'register'})

            self.connected = True

            # 使用信号更新UI，避免跨线程访问
            self.reconnect_success_signal.emit()
            self.update_log_signal.emit("✅ 重新连接成功!")

            # 启动接收线程
            threading.Thread(target=self.receive_loop, daemon=True).start()

            # 刷新主机列表
            self.send_json({'type': 'controller', 'action': 'list_hosts'})

        except Exception as e:
            self.update_log_signal.emit(f"❌ 重连失败: {e}")
            if self.auto_reconnect:
                self.update_log_signal.emit("🔄 10秒后再次尝试...")
                threading.Timer(10.0, self.try_reconnect).start()

    def on_reconnect_success(self):
        """重连成功后更新UI - 在主线程中执行"""
        self.connect_btn.setText("🔌 断开连接")
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        self.ip_input.setEnabled(False)
        self.statusBar().showMessage(f'🟢 已连接到 {self.server_ip}:{self.server_port}')

    def receive_loop(self):
        """接收消息循环"""
        while self.connected:
            try:
                data = self.recv_json()
                if not data:
                    break

                msg_type = data.get('type')

                # 响应心跳
                if msg_type == 'ping':
                    try:
                        self.send_json({'type': 'pong'})
                    except:
                        break
                    continue

                if msg_type == 'host_list':
                    hosts = data.get('hosts', [])
                    self.update_host_list_signal.emit(hosts)

                elif msg_type == 'screenshot':
                    img_b64 = data.get('image')
                    agent_id = data.get('agent_id', 'Unknown')
                    img_data = base64.b64decode(img_b64)
                    self.update_image_signal.emit(img_data, agent_id)
                    self.update_log_signal.emit(f"[{agent_id}] 收到截图 ({len(img_data)} bytes)")

                elif msg_type == 'video_frame':
                    # 只在视频流状态时才更新视频帧
                    if self.video_streaming:
                        img_b64 = data.get('image')
                        agent_id = data.get('agent_id', 'Unknown')
                        img_data = base64.b64decode(img_b64)
                        self.update_image_signal.emit(img_data, agent_id)

                elif msg_type == 'command_result':
                    agent_id = data.get('agent_id', 'Unknown')
                    command = data.get('command', '')
                    output = data.get('output', '')
                    self.update_log_signal.emit(f"\n[{agent_id}] 命令: {command}\n输出:\n{output}\n{'-' * 60}")

                elif msg_type == 'error':
                    message = data.get('message', 'Unknown error')
                    self.update_log_signal.emit(f"⚠️ 错误: {message}")

                elif msg_type == 'drives_list':
                    # 驱动器列表响应
                    drives = data.get('drives', [])
                    error = data.get('error', '')
                    if error:
                        self.update_log_signal.emit(f"❌ 获取磁盘错误: {error}")
                    else:
                        self.update_drives_list(drives)

                elif msg_type == 'file_list':
                    # 文件列表响应
                    path = data.get('path', '')
                    items = data.get('items', [])
                    error = data.get('error', '')
                    if error:
                        self.update_log_signal.emit(f"❌ 文件列表错误: {error}")
                    else:
                        self.update_file_list_signal.emit(path, items)

                elif msg_type == 'file_open':
                    # 文件打开响应
                    filepath = data.get('filepath', '')
                    filename = data.get('filename', '')
                    content_b64 = data.get('content', '')
                    error = data.get('error', '')
                    if error:
                        self.update_log_signal.emit(f"❌ 打开文件错误: {error}")
                    else:
                        # 解码文件内容
                        try:
                            content = base64.b64decode(content_b64).decode('utf-8', errors='replace')
                            self.show_file_content_signal.emit(filepath, filename, content)
                        except Exception as e:
                            self.update_log_signal.emit(f"❌ 解码文件内容错误: {e}")

                elif msg_type == 'file_download':
                    # 文件下载响应
                    filepath = data.get('filepath', '')
                    filename = data.get('filename', '')
                    content_b64 = data.get('content', '')
                    error = data.get('error', '')
                    if error:
                        self.update_log_signal.emit(f"❌ 下载文件错误: {error}")
                    else:
                        self.save_downloaded_file(filename, content_b64)

                elif msg_type == 'file_upload':
                    # 文件上传响应
                    filepath = data.get('filepath', '')
                    error = data.get('error', '')
                    if error:
                        self.update_log_signal.emit(f"❌ 上传文件错误: {error}")
                    else:
                        self.update_log_signal.emit(f"✅ 文件上传成功: {filepath}")
                        # 刷新文件列表
                        QTimer.singleShot(500, self.browse_remote_files)

                elif msg_type == 'file_delete':
                    # 文件删除响应
                    filepath = data.get('filepath', '')
                    error = data.get('error', '')
                    if error:
                        self.update_log_signal.emit(f"❌ 删除失败: {error}")
                    else:
                        self.update_log_signal.emit(f"✅ 删除成功: {filepath}")
                        # 刷新文件列表
                        QTimer.singleShot(500, self.browse_remote_files)

                elif msg_type == 'folder_create':
                    # 文件夹创建响应
                    folderpath = data.get('folderpath', '')
                    error = data.get('error', '')
                    if error:
                        self.update_log_signal.emit(f"❌ 创建文件夹失败: {error}")
                    else:
                        self.update_log_signal.emit(f"✅ 文件夹创建成功: {folderpath}")
                        # 刷新文件列表
                        QTimer.singleShot(500, self.browse_remote_files)

            except socket.timeout:
                # 超时，继续等待
                continue
            except Exception as e:
                if self.connected:
                    self.update_log_signal.emit(f"❌ 接收错误: {e}")
                break

        if self.connected:
            self.disconnect_from_server(user_initiated=False)

    def update_host_list(self, hosts):
        """更新主机列表"""
        self.current_hosts = hosts  # 保存当前主机列表
        self.host_list.clear()
        for host in hosts:
            agent_id = host['id']
            # 优先使用本地保存的自定义名称，其次使用agent上报的名称
            if agent_id in self.host_name_mapping:
                display_name = self.host_name_mapping[agent_id]
            else:
                display_name = host.get('custom_name', host.get('hostname', 'Unknown'))

            item_text = f"{display_name} ({host['ip']})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, agent_id)
            self.host_list.addItem(item)

        self.append_log(f"主机列表已更新: {len(hosts)} 台在线")

    def update_image(self, img_data, agent_id):
        """更新图像显示"""
        pixmap = QPixmap()
        pixmap.loadFromData(img_data)

        # 保存原始图像尺寸（用于坐标转换）
        self.original_image_width = pixmap.width()
        self.original_image_height = pixmap.height()

        # 缩放图像以适应标签大小
        scaled_pixmap = pixmap.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_label.setPixmap(scaled_pixmap)
        self.current_host_label.setText(f"当前显示: {agent_id}")

    def append_log(self, text):
        """添加日志"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_output.append(f"[{timestamp}] {text}")
        self.log_output.moveCursor(QTextCursor.End)

    def get_selected_targets(self, show_warning=True):
        """获取选中的目标主机"""
        selected_items = self.host_list.selectedItems()
        if not selected_items:
            if show_warning:
                QMessageBox.warning(self, "提示", "请先选择要控制的主机")
            return []

        targets = [item.data(Qt.UserRole) for item in selected_items]
        return targets

    def refresh_hosts(self):
        """刷新主机列表"""
        if not self.connected:
            QMessageBox.warning(self, "提示", "请先连接到服务器")
            return

        self.send_json({'type': 'controller', 'action': 'list_hosts'})
        self.append_log("正在刷新主机列表...")

    def select_all_hosts(self):
        """全选主机"""
        self.host_list.selectAll()

    def send_screenshot(self):
        """发送截图命令"""
        targets = self.get_selected_targets()
        if not targets:
            return

        self.send_json({
            'type': 'controller',
            'action': 'screenshot',
            'targets': targets
        })

        self.append_log(f"已发送截图命令到 {len(targets)} 台主机")

    def start_video(self):
        """开始视频流"""
        targets = self.get_selected_targets()
        if not targets:
            return

        if len(targets) > 1:
            QMessageBox.warning(self, "提示", "视频流只能选择一台主机")
            return

        self.send_json({
            'type': 'controller',
            'action': 'start_video',
            'targets': targets,
            'quality': self.video_quality
        })

        # 设置视频流状态
        self.video_streaming = True
        self.current_video_target = targets[0]

        self.start_video_btn.setEnabled(False)
        self.stop_video_btn.setEnabled(True)
        self.append_log(f"已开始视频流: {targets[0]}")

    def stop_video(self):
        """停止视频流"""
        # 如果没有视频流在运行，使用当前选中的主机
        if self.video_streaming and self.current_video_target:
            targets = [self.current_video_target]
        else:
            targets = self.get_selected_targets()
            if not targets:
                # 如果没有选中主机，直接重置按钮状态
                self.start_video_btn.setEnabled(True)
                self.stop_video_btn.setEnabled(False)
                self.video_streaming = False
                self.current_video_target = None
                return

        self.send_json({
            'type': 'controller',
            'action': 'stop_video',
            'targets': targets
        })

        # 重置视频流状态
        self.video_streaming = False
        self.current_video_target = None

        # 清除图像显示
        self.image_label.clear()
        self.image_label.setText("📺 等待视频流或截图...\n\n点击'开始视频'或'截图'按钮开始")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.current_host_label.setText("📍 当前显示: 无")

        self.start_video_btn.setEnabled(True)
        self.stop_video_btn.setEnabled(False)
        self.append_log(f"✅ 已停止视频流")

    def send_command(self):
        """发送命令"""
        targets = self.get_selected_targets()
        if not targets:
            return

        command = self.cmd_input.text().strip()
        if not command:
            QMessageBox.warning(self, "提示", "请输入命令")
            return

        as_admin = self.admin_checkbox.isChecked()

        self.send_json({
            'type': 'controller',
            'action': 'run_command',
            'targets': targets,
            'command': command,
            'as_admin': as_admin
        })

        admin_text = " (管理员权限)" if as_admin else ""
        self.append_log(f"已发送命令到 {len(targets)} 台主机{admin_text}: {command}")
        self.cmd_input.clear()

    def send_json(self, data):
        """发送JSON数据"""
        try:
            if not self.sock:
                return False
            msg = json.dumps(data).encode('utf-8')
            length = len(msg)
            self.sock.sendall(length.to_bytes(4, 'big') + msg)
            return True
        except Exception as e:
            # 使用信号发送日志，避免线程安全问题
            self.update_log_signal.emit(f"发送数据错误: {e}")
            return False

    def recv_json(self):
        """接收JSON数据"""
        try:
            raw_len = self.sock.recv(4)
            if not raw_len or len(raw_len) < 4:
                return None

            msg_len = int.from_bytes(raw_len, 'big')

            msg = b''
            while len(msg) < msg_len:
                chunk = self.sock.recv(min(msg_len - len(msg), 4096))
                if not chunk:
                    return None
                msg += chunk

            return json.loads(msg.decode('utf-8'))
        except Exception as e:
            return None

    def load_custom_commands(self):
        """加载自定义命令"""
        try:
            with open('custom_commands.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {
                "查看IP配置": "ipconfig",
                "查看系统信息": "systeminfo",
                "查看进程列表": "tasklist",
                "查看磁盘信息": "wmic logicaldisk get name,size,freespace"
            }

    def save_custom_commands(self):
        """保存自定义命令"""
        try:
            with open('custom_commands.json', 'w', encoding='utf-8') as f:
                json.dump(self.custom_commands, f, ensure_ascii=False, indent=2)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"保存命令失败: {e}")

    def load_host_name_mapping(self):
        """加载主机名映射"""
        try:
            with open('host_name_mapping.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}

    def save_host_name_mapping(self):
        """保存主机名映射"""
        try:
            with open('host_name_mapping.json', 'w', encoding='utf-8') as f:
                json.dump(self.host_name_mapping, f, ensure_ascii=False, indent=2)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"保存主机名映射失败: {e}")

    def manage_commands(self):
        """管理自定义命令"""
        dialog = QDialog(self)
        dialog.setWindowTitle("管理自定义命令")
        dialog.setGeometry(200, 200, 600, 400)

        layout = QVBoxLayout(dialog)

        # 命令列表
        cmd_list = QListWidget()
        for cmd_name, cmd_value in self.custom_commands.items():
            cmd_list.addItem(f"{cmd_name}: {cmd_value}")
        layout.addWidget(cmd_list)

        # 按钮
        btn_layout = QHBoxLayout()

        add_btn = QPushButton("添加")
        add_btn.clicked.connect(lambda: self.add_command(cmd_list))
        btn_layout.addWidget(add_btn)

        del_btn = QPushButton("删除")
        del_btn.clicked.connect(lambda: self.delete_command(cmd_list))
        btn_layout.addWidget(del_btn)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.close)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)
        dialog.exec_()

    def add_command(self, cmd_list):
        """添加自定义命令"""
        name, ok1 = QInputDialog.getText(self, "添加命令", "命令名称:")
        if ok1 and name:
            command, ok2 = QInputDialog.getText(self, "添加命令", "命令内容:")
            if ok2 and command:
                self.custom_commands[name] = command
                self.save_custom_commands()
                cmd_list.addItem(f"{name}: {command}")
                self.cmd_combo.addItem(name)
                QMessageBox.information(self, "成功", "命令已添加")

    def delete_command(self, cmd_list):
        """删除自定义命令"""
        current_item = cmd_list.currentItem()
        if current_item:
            text = current_item.text()
            name = text.split(':')[0].strip()
            if name in self.custom_commands:
                del self.custom_commands[name]
                self.save_custom_commands()
                cmd_list.takeItem(cmd_list.currentRow())
                index = self.cmd_combo.findText(name)
                if index >= 0:
                    self.cmd_combo.removeItem(index)
                QMessageBox.information(self, "成功", "命令已删除")

    def on_cmd_selected(self, cmd_name):
        """选择自定义命令"""
        if cmd_name in self.custom_commands:
            self.cmd_input.setText(self.custom_commands[cmd_name])

    def on_quality_changed(self, index):
        """视频质量改变"""
        quality_map = {0: 'low', 1: 'medium', 2: 'high', 3: 'ultra'}
        self.video_quality = quality_map[index]

    def toggle_remote_control(self):
        """切换远程鼠标控制模式"""
        self.remote_control_mode = self.remote_control_btn.isChecked()
        if self.remote_control_mode:
            self.remote_control_btn.setText("🖱 鼠标控制 (已启用)")
            self.append_log("✅ 远程鼠标控制已启用 - 在屏幕显示区域点击鼠标进行控制")
        else:
            self.remote_control_btn.setText("🖱 鼠标控制")
            self.append_log("❌ 远程鼠标控制已禁用")

    def toggle_keyboard_control(self):
        """切换远程键盘控制模式"""
        self.keyboard_control_mode = self.keyboard_control_btn.isChecked()
        if self.keyboard_control_mode:
            self.keyboard_control_btn.setText("⌨️ 键盘控制 (已启用)")
            self.append_log("✅ 远程键盘控制已启用 - 在主窗口按键将发送到远程主机")
            # 设置焦点到主窗口以接收键盘事件
            self.setFocus()
        else:
            self.keyboard_control_btn.setText("⌨️ 键盘控制")
            self.append_log("❌ 远程键盘控制已禁用")

    def on_image_mouse_press(self, event):
        """图像区域鼠标按下"""
        if not self.remote_control_mode:
            return

        selected = self.get_selected_targets(show_warning=False)
        if len(selected) != 1:
            return

        # 计算相对坐标
        x, y = self.get_relative_coords(event.x(), event.y())
        if x is None:
            return

        # 发送鼠标点击（包含坐标）
        button = 'left' if event.button() == Qt.LeftButton else 'right'
        self.send_json({
            'type': 'controller',
            'action': 'mouse_click',
            'targets': selected,
            'button': button,
            'clicks': 1,
            'x': x,
            'y': y
        })

    def on_image_mouse_move(self, event):
        """图像区域鼠标移动"""
        if not self.remote_control_mode or not (event.buttons() & Qt.LeftButton):
            return

        selected = self.get_selected_targets(show_warning=False)
        if len(selected) != 1:
            return

        # 计算相对坐标
        x, y = self.get_relative_coords(event.x(), event.y())
        if x is None:
            return

        # 发送鼠标移动
        self.send_json({
            'type': 'controller',
            'action': 'mouse_move',
            'targets': selected,
            'x': x,
            'y': y
        })

    def on_image_wheel(self, event):
        """图像区域鼠标滚轮"""
        if not self.remote_control_mode:
            return

        selected = self.get_selected_targets(show_warning=False)
        if len(selected) != 1:
            return

        # 发送滚轮事件
        delta = event.angleDelta().y() // 120
        self.send_json({
            'type': 'controller',
            'action': 'mouse_scroll',
            'targets': selected,
            'dx': 0,
            'dy': delta
        })

    def show_host_context_menu(self, position):
        """显示主机列表右键菜单"""
        item = self.host_list.itemAt(position)
        if not item:
            return

        menu = QMenu()
        rename_action = menu.addAction("🏷 修改显示名称")

        action = menu.exec_(self.host_list.mapToGlobal(position))

        if action == rename_action:
            self.rename_host(item)

    def rename_host(self, item):
        """修改主机显示名称"""
        agent_id = item.data(Qt.UserRole)

        # 获取当前名称
        current_name = ""
        if agent_id in self.host_name_mapping:
            current_name = self.host_name_mapping[agent_id]
        else:
            # 从current_hosts中查找
            for host in self.current_hosts:
                if host['id'] == agent_id:
                    current_name = host.get('custom_name', host.get('hostname', ''))
                    break

        # 弹出输入对话框
        new_name, ok = QInputDialog.getText(
            self,
            "修改显示名称",
            f"请输入新的显示名称:\n(Agent ID: {agent_id})",
            text=current_name
        )

        if ok and new_name.strip():
            # 保存到映射
            self.host_name_mapping[agent_id] = new_name.strip()
            self.save_host_name_mapping()

            # 更新显示
            for host in self.current_hosts:
                if host['id'] == agent_id:
                    host_ip = host.get('ip', 'Unknown')
                    item.setText(f"{new_name.strip()} ({host_ip})")
                    break

            self.append_log(f"已修改主机 {agent_id} 的显示名称为: {new_name.strip()}")

    def get_relative_coords(self, x, y):
        """获取相对于原始屏幕的坐标（完全修复版）"""
        pixmap = self.image_label.pixmap()
        if not pixmap:
            return None, None

        # 获取label尺寸
        label_w = self.image_label.width()
        label_h = self.image_label.height()

        # 获取显示的pixmap尺寸（已经缩放过的）
        pixmap_w = pixmap.width()
        pixmap_h = pixmap.height()

        # 计算pixmap在label中的实际显示位置（居中显示）
        offset_x = (label_w - pixmap_w) / 2
        offset_y = (label_h - pixmap_h) / 2

        # 转换为pixmap上的坐标
        img_x = x - offset_x
        img_y = y - offset_y

        # 检查是否在图像范围内
        if img_x < 0 or img_y < 0 or img_x > pixmap_w or img_y > pixmap_h:
            return None, None

        # 转换为原始屏幕坐标
        # pixmap是缩放后的图像，需要转换回原始尺寸
        scale_x = self.original_image_width / pixmap_w
        scale_y = self.original_image_height / pixmap_h

        original_x = int(img_x * scale_x)
        original_y = int(img_y * scale_y)

        return original_x, original_y

    def on_host_clicked(self, item):
        """主机被点击时"""
        # 只在磁盘列表为空时才刷新
        if self.drive_combo.count() == 0:
            self.refresh_drives()

    def refresh_drives(self):
        """刷新磁盘驱动器列表"""
        selected = self.get_selected_targets(show_warning=False)
        if len(selected) != 1:
            return

        self.send_json({
            'type': 'controller',
            'action': 'get_drives',
            'targets': selected
        })

        self.append_log(f"🔄 正在获取磁盘列表...")

    def update_drives_list(self, drives):
        """更新驱动器列表"""
        self.drive_combo.clear()

        for drive in drives:
            name = drive['name']
            path = drive['path']
            dtype = drive.get('type', '本地磁盘')
            total = drive.get('total', 0)
            free = drive.get('free', 0)

            # 格式化容量显示
            if total > 0:
                total_gb = total / (1024 ** 3)
                free_gb = free / (1024 ** 3)
                used_percent = ((total - free) / total * 100) if total > 0 else 0
                display_text = f"💾 {name}: ({dtype}) - {free_gb:.1f}GB可用 / {total_gb:.1f}GB ({used_percent:.0f}%已用)"
            else:
                display_text = f"💾 {name}: ({dtype})"

            self.drive_combo.addItem(display_text, path)

        self.append_log(f"✅ 获取到 {len(drives)} 个磁盘驱动器")

    def on_drive_selected(self, index):
        """选择磁盘驱动器"""
        if index < 0:
            return

        drive_path = self.drive_combo.itemData(index)
        if drive_path:
            self.current_path_input.setText(drive_path)
            self.browse_remote_files()

    def browse_remote_files(self):
        """浏览远程文件"""
        selected = self.get_selected_targets()
        if len(selected) != 1:
            QMessageBox.warning(self, "提示", "请选择一台主机")
            return

        path = self.current_path_input.text().strip()
        if not path:
            QMessageBox.warning(self, "提示", "请输入路径或选择磁盘")
            return

        self.send_json({
            'type': 'controller',
            'action': 'list_files',
            'targets': selected,
            'path': path
        })

        self.append_log(f"📂 浏览目录: {path}")

    def update_file_list(self, path, items):
        """更新文件列表"""
        try:
            self.file_list.clear()
            self.current_path_input.setText(path)

            # ✅ 检查 items 是否为列表
            if not isinstance(items, list):
                self.append_log(f"❌ 文件列表格式错误")
                return

            for item in items:
                # ✅ 安全获取数据
                if not isinstance(item, dict):
                    continue

                name = item.get('name', '')
                item_type = item.get('type', '')
                size = item.get('size', 0)

                if not name or not item_type:
                    continue

                if item_type == 'folder':
                    icon = "📁"
                    display_text = f"{icon} {name}"
                else:
                    icon = "📄"
                    size_str = self.format_file_size(size)
                    display_text = f"{icon} {name} ({size_str})"

                list_item = QListWidgetItem(display_text)
                # ✅ 存储完整数据
                list_item.setData(Qt.UserRole, {
                    'name': name,
                    'type': item_type,
                    'path': path,
                    'size': size
                })
                self.file_list.addItem(list_item)

            self.append_log(f"✅ 文件列表已更新: {len(items)} 项")
        except Exception as e:
            self.append_log(f"❌ 更新文件列表错误: {e}")

    def format_file_size(self, size):
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"

    def on_file_double_click(self, item):
        """文件双击事件"""
        try:
            # ✅ 检查 data 是否存在
            data = item.data(Qt.UserRole)
            if not data:
                return

            # ✅ 检查是否为文件夹
            if data.get('type') != 'folder':
                return

            # 进入文件夹
            current_path = data.get('path', '')
            folder_name = data.get('name', '')

            if not current_path or not folder_name:
                return

            if folder_name == '..':
                # ✅ 返回上级目录，处理根目录情况
                new_path = os.path.dirname(current_path.rstrip('\\'))
                # 如果是根目录（如 C:），添加反斜杠
                if len(new_path) == 2 and new_path[1] == ':':
                    new_path += '\\'
            else:
                # ✅ 进入子目录
                new_path = os.path.join(current_path, folder_name)

            self.current_path_input.setText(new_path)
            self.browse_remote_files()
        except Exception as e:
            self.append_log(f"❌ 双击错误: {e}")

    def show_file_context_menu(self, position):
        """显示文件右键菜单"""
        try:
            item = self.file_list.itemAt(position)

            # 获取当前路径
            current_path = self.current_path_input.text().strip()
            if not current_path:
                return

            menu = QMenu()
            open_action = None
            download_action = None
            delete_action = None
            item_data = None

            if item:
                # ✅ 安全获取数据
                item_data = item.data(Qt.UserRole)

                if item_data:
                    # 点击了文件或文件夹
                    item_type = item_data.get('type', '')
                    item_name = item_data.get('name', '')

                    if item_type == 'file':
                        # ✅ 添加打开查看文件选项
                        open_action = menu.addAction("👁️ 打开查看")
                        menu.addSeparator()
                        download_action = menu.addAction("⬇️ 下载文件")
                        delete_action = menu.addAction("🗑️ 删除文件")
                    elif item_type == 'folder' and item_name != '..':
                        delete_action = menu.addAction("🗑️ 删除文件夹")

                    if download_action or delete_action:
                        menu.addSeparator()

            # 通用操作（总是显示）
            upload_action = menu.addAction("⬆️ 上传文件")
            create_folder_action = menu.addAction("📁 新建文件夹")

            action = menu.exec_(self.file_list.mapToGlobal(position))

            if not action:
                return

            # ✅ 安全执行操作
            if action == open_action and open_action and item_data:
                self.open_file(item_data)
            elif action == download_action and download_action and item_data:
                self.download_file(item_data)
            elif action == delete_action and delete_action and item_data:
                self.delete_file(item_data)
            elif action == upload_action:
                self.upload_file(current_path)
            elif action == create_folder_action:
                self.create_folder(current_path)
        except Exception as e:
            self.append_log(f"❌ 右键菜单错误: {e}")

    def open_file(self, data):
        """打开查看文件"""
        try:
            selected = self.get_selected_targets(show_warning=False)
            if len(selected) != 1:
                return

            # ✅ 安全获取路径和文件名
            path = data.get('path', '')
            name = data.get('name', '')
            size = data.get('size', 0)

            if not path or not name:
                self.append_log("❌ 打开失败: 路径或文件名为空")
                return

            filepath = os.path.join(path, name)

            # ✅ 检查文件大小，避免打开过大的文件
            max_size = 10 * 1024 * 1024  # 10MB
            if size > max_size:
                reply = QMessageBox.question(
                    self,
                    "文件过大",
                    f"文件大小为 {self.format_file_size(size)}，可能需要较长时间加载。\n是否继续打开？",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return

            # 发送打开文件请求
            self.send_json({
                'type': 'controller',
                'action': 'open_file',
                'targets': selected,
                'filepath': filepath
            })

            self.append_log(f"👁️ 正在打开文件: {filepath}")
        except Exception as e:
            self.append_log(f"❌ 打开文件错误: {e}")

    def download_file(self, data):
        """下载文件"""
        try:
            selected = self.get_selected_targets(show_warning=False)
            if len(selected) != 1:
                return

            # ✅ 安全获取路径和文件名
            path = data.get('path', '')
            name = data.get('name', '')

            if not path or not name:
                self.append_log("❌ 下载失败: 路径或文件名为空")
                return

            filepath = os.path.join(path, name)

            self.send_json({
                'type': 'controller',
                'action': 'download_file',
                'targets': selected,
                'filepath': filepath
            })

            self.append_log(f"⬇️ 正在下载: {filepath}")
        except Exception as e:
            self.append_log(f"❌ 下载文件错误: {e}")

    def save_downloaded_file(self, filename, content_b64):
        """保存下载的文件"""
        try:
            # 弹出保存对话框
            save_path, _ = QFileDialog.getSaveFileName(self, "保存文件", filename)
            if save_path:
                content = base64.b64decode(content_b64)
                with open(save_path, 'wb') as f:
                    f.write(content)
                self.append_log(f"✅ 文件已保存: {save_path}")
        except Exception as e:
            self.append_log(f"❌ 保存文件错误: {e}")

    def upload_file(self, remote_path):
        """上传文件"""
        selected = self.get_selected_targets(show_warning=False)
        if len(selected) != 1:
            return

        # 选择本地文件
        local_file, _ = QFileDialog.getOpenFileName(self, "选择要上传的文件")
        if not local_file:
            return

        try:
            with open(local_file, 'rb') as f:
                content_b64 = base64.b64encode(f.read()).decode('utf-8')

            filename = os.path.basename(local_file)
            remote_filepath = os.path.join(remote_path, filename)

            self.send_json({
                'type': 'controller',
                'action': 'upload_file',
                'targets': selected,
                'filepath': remote_filepath,
                'content': content_b64
            })

            self.append_log(f"⬆️ 正在上传: {filename} -> {remote_filepath}")
        except Exception as e:
            self.append_log(f"❌ 上传文件错误: {e}")

    def delete_file(self, data):
        """删除文件"""
        try:
            selected = self.get_selected_targets(show_warning=False)
            if len(selected) != 1:
                return

            # ✅ 安全获取路径和文件名
            path = data.get('path', '')
            name = data.get('name', '')

            if not path or not name:
                self.append_log("❌ 删除失败: 路径或文件名为空")
                return

            filepath = os.path.join(path, name)

            reply = QMessageBox.question(self, "确认删除",
                                         f"确定要删除 {name} 吗？",
                                         QMessageBox.Yes | QMessageBox.No)

            if reply == QMessageBox.Yes:
                self.send_json({
                    'type': 'controller',
                    'action': 'delete_file',
                    'targets': selected,
                    'filepath': filepath
                })

                self.append_log(f"🗑️ 正在删除: {filepath}")
        except Exception as e:
            self.append_log(f"❌ 删除文件错误: {e}")

    def create_folder(self, remote_path):
        """创建文件夹"""
        try:
            selected = self.get_selected_targets(show_warning=False)
            if len(selected) != 1:
                return

            # ✅ 检查远程路径
            if not remote_path:
                self.append_log("❌ 创建文件夹失败: 路径为空")
                return

            folder_name, ok = QInputDialog.getText(self, "新建文件夹", "请输入文件夹名称:")
            if ok and folder_name:
                # ✅ 验证文件夹名称
                folder_name = folder_name.strip()
                if not folder_name:
                    self.append_log("❌ 创建文件夹失败: 文件夹名称为空")
                    return

                # ✅ 检查非法字符
                invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
                if any(char in folder_name for char in invalid_chars):
                    self.append_log(f"❌ 创建文件夹失败: 文件夹名称包含非法字符")
                    return

                folderpath = os.path.join(remote_path, folder_name)

                self.send_json({
                    'type': 'controller',
                    'action': 'create_folder',
                    'targets': selected,
                    'folderpath': folderpath
                })

                self.append_log(f"📁 正在创建文件夹: {folderpath}")
        except Exception as e:
            self.append_log(f"❌ 创建文件夹错误: {e}")

    def keyPressEvent(self, event):
        """键盘按下事件"""
        if not self.keyboard_control_mode:
            super().keyPressEvent(event)
            return

        selected = self.get_selected_targets(show_warning=False)
        if len(selected) != 1:
            super().keyPressEvent(event)
            return

        # 获取按键
        key = event.text()
        if not key:
            # 处理特殊键
            key_map = {
                Qt.Key_Return: 'enter',
                Qt.Key_Enter: 'enter',
                Qt.Key_Backspace: 'backspace',
                Qt.Key_Tab: 'tab',
                Qt.Key_Escape: 'esc',
                Qt.Key_Delete: 'delete',
                Qt.Key_Home: 'home',
                Qt.Key_End: 'end',
                Qt.Key_PageUp: 'pageup',
                Qt.Key_PageDown: 'pagedown',
                Qt.Key_Up: 'up',
                Qt.Key_Down: 'down',
                Qt.Key_Left: 'left',
                Qt.Key_Right: 'right',
                Qt.Key_F1: 'f1',
                Qt.Key_F2: 'f2',
                Qt.Key_F3: 'f3',
                Qt.Key_F4: 'f4',
                Qt.Key_F5: 'f5',
                Qt.Key_F6: 'f6',
                Qt.Key_F7: 'f7',
                Qt.Key_F8: 'f8',
                Qt.Key_F9: 'f9',
                Qt.Key_F10: 'f10',
                Qt.Key_F11: 'f11',
                Qt.Key_F12: 'f12',
            }
            key = key_map.get(event.key(), '')

        if key:
            # 发送键盘输入
            self.send_json({
                'type': 'controller',
                'action': 'keyboard_type',
                'targets': selected,
                'text': key
            })
            self.append_log(f"⌨️ 发送按键: {key}")

        event.accept()

    def show_file_content(self, filepath, filename, content):
        """显示文件内容"""
        try:
            # 创建文件查看对话框
            dialog = QDialog(self)
            dialog.setWindowTitle(f"查看文件 - {filename}")
            dialog.resize(800, 600)

            layout = QVBoxLayout()

            # 文件路径标签
            path_label = QLabel(f"📄 文件路径: {filepath}")
            path_label.setStyleSheet("font-weight: bold; padding: 5px;")
            layout.addWidget(path_label)

            # 文本编辑器（只读）
            text_edit = QTextEdit()
            text_edit.setPlainText(content)
            text_edit.setReadOnly(True)
            text_edit.setStyleSheet("""
                QTextEdit {
                    font-family: 'Consolas', 'Monaco', monospace;
                    font-size: 10pt;
                    background-color: #f5f5f5;
                    border: 1px solid #ddd;
                }
            """)
            layout.addWidget(text_edit)

            # 按钮区域
            button_layout = QHBoxLayout()

            # 复制按钮
            copy_btn = QPushButton("📋 复制全部")
            copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(content))
            button_layout.addWidget(copy_btn)

            # 另存为按钮
            save_btn = QPushButton("💾 另存为")
            save_btn.clicked.connect(lambda: self.save_file_content(filename, content))
            button_layout.addWidget(save_btn)

            button_layout.addStretch()

            # 关闭按钮
            close_btn = QPushButton("关闭")
            close_btn.clicked.connect(dialog.close)
            button_layout.addWidget(close_btn)

            layout.addLayout(button_layout)

            dialog.setLayout(layout)
            dialog.exec_()

            self.append_log(f"✅ 文件已打开: {filename}")
        except Exception as e:
            self.append_log(f"❌ 显示文件内容错误: {e}")

    def save_file_content(self, filename, content):
        """保存文件内容"""
        try:
            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "另存为",
                filename,
                "所有文件 (*.*)"
            )

            if save_path:
                with open(save_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.append_log(f"✅ 文件已保存: {save_path}")
        except Exception as e:
            self.append_log(f"❌ 保存文件错误: {e}")

    def closeEvent(self, event):
        """关闭窗口事件"""
        if self.connected:
            self.disconnect_from_server(user_initiated=True)
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)

    # 设置应用样式
    app.setStyle('Fusion')

    window = ControllerGUI()
    window.show()

    sys.exit(app.exec_())
