"""
六軸機械手臂控制界面
修正視窗縮放問題，優化顯示比例
"""

import sys
import time
import json
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
                            QPushButton, QLabel, QSlider, QGroupBox, QTabWidget,
                            QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit,
                            QTableWidget, QTableWidgetItem, QHeaderView,
                            QMessageBox, QInputDialog, QFileDialog, QCheckBox,
                            QScrollArea, QSizePolicy)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot, QSize
from PyQt5.QtGui import QFont, QColor

# 導入機械手臂控制器
try:
    from robotic_arm_controller import RoboticArmController, Position
    ARM_AVAILABLE = True
except ImportError:
    ARM_AVAILABLE = False
    print("⚠️ 機械手臂控制模組未找到")
    
    # 模擬類
    class Position:
        def __init__(self, j1=180, j2=180, j3=90, j4=90, j5=90, j6=73):
            self.joint1, self.joint2, self.joint3 = j1, j2, j3
            self.joint4, self.joint5, self.joint6 = j4, j5, j6
        
        def to_list(self):
            return [self.joint1, self.joint2, self.joint3, 
                   self.joint4, self.joint5, self.joint6]
        
        @classmethod
        def from_list(cls, angles):
            return cls(*angles)


class ArmControlWidget(QWidget):
    """機械手臂控制界面 - 修正版"""
    
    # 信號：動作完成
    action_completed = pyqtSignal(str, bool)
    
    def __init__(self, arm_controller=None, parent=None):
        super().__init__(parent)
        
        # 機械手臂控制器
        self.arm_controller = arm_controller
        self.is_simulation_mode = (arm_controller is None)
        
        # 緊急停止標誌
        self.emergency_stopped = False
        
        # 初始化界面
        self.init_ui()
        
        # 啟動狀態更新
        self.start_status_timer()
        
        # 模擬模式，顯示警告
        if self.is_simulation_mode:
            self.add_log("⚠️ 模擬模式：機械手臂未連接，所有操作僅在界面模擬")
        else:
            self.add_log("✅ 機械手臂控制界面已就緒")
    
    def init_ui(self):
        """初始化用戶界面 - 修正版"""
        # 主佈局使用固定比例
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        main_layout.setSpacing(5)
        main_layout.setContentsMargins(8, 8, 8, 8)
        
        # 標題欄 
        title_layout = QHBoxLayout()
        
        title_label = QLabel("🤖 六軸機械手臂控制面板")
        title_label.setFont(QFont("Microsoft JhengHei", 12, QFont.Bold))
        title_label.setStyleSheet("color: #2196F3; padding: 3px;")
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        # 連接狀態
        self.connection_label = QLabel()
        self.connection_label.setFont(QFont("Microsoft JhengHei", 9))
        self.update_connection_status()
        title_layout.addWidget(self.connection_label)
        
        main_layout.addLayout(title_layout)
        
        # 緊急停止控制 
        emergency_layout = QHBoxLayout()
        emergency_layout.setSpacing(8)
        
        self.emergency_btn = QPushButton("🚨 緊急停止")
        self.emergency_btn.setFixedHeight(45)
        self.emergency_btn.setFont(QFont("Microsoft JhengHei", 11, QFont.Bold))
        self.emergency_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF5722;
                color: white;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #E64A19;
            }
        """)
        self.emergency_btn.clicked.connect(self.emergency_stop)
        emergency_layout.addWidget(self.emergency_btn, 2)
        
        self.resume_btn = QPushButton("▶️ 恢復運行")
        self.resume_btn.setFixedHeight(45)
        self.resume_btn.setFont(QFont("Microsoft JhengHei", 11, QFont.Bold))
        self.resume_btn.setStyleSheet("""
            QPushButton {
                background-color: #009688;
                color: white;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #00796B;
            }
            QPushButton:disabled {
                background-color: #B0BEC5;
            }
        """)
        self.resume_btn.clicked.connect(self.resume_operation)
        self.resume_btn.setEnabled(False)
        emergency_layout.addWidget(self.resume_btn, 1)
        
        main_layout.addLayout(emergency_layout)
        
        # 先創建日誌區域
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(80)
        self.log_text.setFont(QFont("Consolas", 8))
        
        # 標籤頁 
        tab_widget = QTabWidget()
        tab_widget.setFont(QFont("Microsoft JhengHei", 9))
        
        tab_widget.addTab(self.create_quick_control_tab(), "⚡ 快速控制")
        tab_widget.addTab(self.create_manual_control_tab(), "🔧 手動控制")
        tab_widget.addTab(self.create_position_manager_tab(), "📍 位置管理")
        tab_widget.addTab(self.create_status_tab(), "📊 狀態監控")
        
        # 標籤頁最大伸展空間
        main_layout.addWidget(tab_widget, 1)
        
        # 日誌區域 
        log_group = QGroupBox("📝 操作日誌")
        log_group.setFont(QFont("Microsoft JhengHei", 9, QFont.Bold))
        log_layout = QVBoxLayout()
        log_layout.setContentsMargins(5, 5, 5, 5)
        
        log_layout.addWidget(self.log_text)
        
        log_btn_layout = QHBoxLayout()
        clear_log_btn = QPushButton("🗑️ 清除")
        clear_log_btn.setFixedHeight(25)
        clear_log_btn.clicked.connect(lambda: self.log_text.clear())
        log_btn_layout.addWidget(clear_log_btn)
        log_btn_layout.addStretch()
        
        log_layout.addLayout(log_btn_layout)
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)

    def goto_defect_area_via_common_path(self, mode: str):
        """快速位置：先走通用移動，再到分類區"""
        if self.is_simulation_mode or not self.arm_controller:
            self.add_log("ℹ️ 模擬模式或未連接硬體")
            return

        mapping = {
            'single': "夾取後到分類一區之路徑二",
            'double': "夾取後到分類二區之路徑二",
            'multiple': "夾取後到分類三區之路徑二",
        }
        target_pos_name = mapping.get(mode)
        if not target_pos_name:
            self.add_log(f"❌ 未知缺陷區模式: {mode}")
            return

        predefined = self.arm_controller.predefined_positions
        if "夾取後通用移動" not in predefined or target_pos_name not in predefined:
            self.add_log(f"❌ 位置未定義")
            return

        self.add_log(f"🚚 快速移動：{target_pos_name}")
        self.arm_controller.move_to_predefined("夾取後通用移動", duration=1.2)
        self.arm_controller.move_to_predefined(target_pos_name, duration=1.2)

    def create_quick_control_tab(self):
        """創建快速控制標籤頁 - 使用ScrollArea"""
        # 使用ScrollArea包裝
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(5, 5, 5, 5)
        widget.setLayout(layout)
        
        # 快速位置 
        quick_pos_group = QGroupBox("📍 快速位置")
        quick_pos_group.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
        quick_pos_layout = QGridLayout()
        quick_pos_layout.setSpacing(6)
        
        quick_positions = [
            ("🏠 原點", lambda: self.goto_predefined('home'), 0, 0, "#2196F3"),
            ("☁️ 安全高位", lambda: self.goto_predefined('safe_high'), 0, 1, "#9C27B0"),
            ("🔍 檢查", lambda: self.goto_predefined('check'), 1, 0, "#FF9800"),
            ("😴 休息", lambda: self.goto_predefined('rest'), 1, 1, "#607D8B"),
            ("🔵 單一缺陷", lambda: self.goto_defect_area_via_common_path('single'), 2, 0, "#2196F3"),
            ("🟡 兩種缺陷", lambda: self.goto_defect_area_via_common_path('double'), 2, 1, "#FF9800"),
            ("🔴 多種缺陷", lambda: self.goto_defect_area_via_common_path('multiple'), 3, 0, "#f44336"),
        ]
        
        for text, func, row, col, color in quick_positions:
            btn = QPushButton(text)
            btn.setFixedHeight(50)
            btn.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    color: white;
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    background-color: {self.darken_color(color)};
                }}
            """)
            btn.clicked.connect(func)
            quick_pos_layout.addWidget(btn, row, col)
        
        quick_pos_group.setLayout(quick_pos_layout)
        layout.addWidget(quick_pos_group)
        
        # 夾爪控制 
        gripper_group = QGroupBox("✋ 夾爪控制")
        gripper_group.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
        gripper_layout = QHBoxLayout()
        gripper_layout.setSpacing(8)
        
        open_gripper_btn = QPushButton("🔓 打開 (73°)")
        open_gripper_btn.setFixedHeight(50)
        open_gripper_btn.setFont(QFont("Microsoft JhengHei", 11, QFont.Bold))
        open_gripper_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #388E3C;
            }
        """)
        open_gripper_btn.clicked.connect(lambda: self.gripper_control('open'))
        gripper_layout.addWidget(open_gripper_btn)
        
        close_gripper_btn = QPushButton("🔒 關閉 (30°)")
        close_gripper_btn.setFixedHeight(50)
        close_gripper_btn.setFont(QFont("Microsoft JhengHei", 11, QFont.Bold))
        close_gripper_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #D32F2F;
            }
        """)
        close_gripper_btn.clicked.connect(lambda: self.gripper_control('close'))
        gripper_layout.addWidget(close_gripper_btn)
        
        gripper_group.setLayout(gripper_layout)
        layout.addWidget(gripper_group)
        
        # 自動分類序列 
        sorting_group = QGroupBox("🤖 自動分類序列")
        sorting_group.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
        sorting_layout = QGridLayout()
        sorting_layout.setSpacing(6)

        sorting_buttons = [
            ("🔵 單一缺陷", 'single', "#2196F3"),
            ("🟡 兩種缺陷", 'double', "#FF9800"),
            ("🔴 多種缺陷", 'multiple', "#f44336"),
            ("🎬 演示序列", 'demo', "#9C27B0"),
        ]

        for i, (text, mode, color) in enumerate(sorting_buttons):
            btn = QPushButton(text)
            btn.setFixedHeight(48)
            btn.setFont(QFont("Microsoft JhengHei", 11, QFont.Bold))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    color: white;
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    background-color: {self.darken_color(color)};
                }}
            """)
            btn.clicked.connect(lambda checked, m=mode: self.execute_sorting_sequence(m))
            sorting_layout.addWidget(btn, i, 0, 1, 2)

        sorting_group.setLayout(sorting_layout)
        layout.addWidget(sorting_group)

        layout.addStretch()
        scroll.setWidget(widget)
        return scroll
    
    def create_manual_control_tab(self):
        """創建手動控制標籤頁 - 使用ScrollArea"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(5, 5, 5, 5)
        widget.setLayout(layout)
        
        # 關節控制
        joint_group = QGroupBox("🔧 關節角度控制")
        joint_group.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
        joint_layout = QGridLayout()
        joint_layout.setSpacing(5)
        
        self.joint_sliders = {}
        self.joint_labels = {}
        
        joints = [
            ("joint1", "基座旋轉", 0, 180, 0),
            ("joint2", "肩部俯仰", 0, 180, 180),
            ("joint3", "手肘彎曲", 0, 180, 90),
            ("joint4", "腕部俯仰", 0, 180, 90),
            ("joint5", "腕部旋轉", 0, 180, 90),
            ("joint6", "夾爪", 30, 73, 73),
        ]
        
        for i, (jid, name, min_v, max_v, default) in enumerate(joints):
            # 名稱
            label = QLabel(name)
            label.setFont(QFont("Microsoft JhengHei", 9))
            label.setMinimumWidth(70)
            joint_layout.addWidget(label, i, 0)
            
            # 角度顯示
            angle_label = QLabel(f"{default}°")
            angle_label.setFont(QFont("Consolas", 9))
            angle_label.setMinimumWidth(40)
            angle_label.setAlignment(Qt.AlignCenter)
            self.joint_labels[jid] = angle_label
            joint_layout.addWidget(angle_label, i, 1)
            
            # 滑桿
            slider = QSlider(Qt.Horizontal)
            slider.setRange(min_v, max_v)
            slider.setValue(default)
            slider.setMinimumWidth(200)
            slider.valueChanged.connect(lambda v, j=jid: self.update_joint_label(j, v))
            self.joint_sliders[jid] = slider
            joint_layout.addWidget(slider, i, 2)
            
            # 快捷按鈕
            btn_layout = QHBoxLayout()
            btn_layout.setSpacing(2)
            
            get_btn = QPushButton("📍")
            get_btn.setToolTip("獲取當前角度")
            get_btn.setFixedSize(30, 25)
            get_btn.clicked.connect(lambda _, j=jid: self.get_current_joint_angle(j))
            btn_layout.addWidget(get_btn)
            
            set_btn = QPushButton("✓")
            set_btn.setToolTip("設置此關節")
            set_btn.setFixedSize(30, 25)
            set_btn.clicked.connect(lambda _, j=jid: self.set_single_joint(j))
            btn_layout.addWidget(set_btn)
            
            joint_layout.addLayout(btn_layout, i, 3)
        
        joint_group.setLayout(joint_layout)
        layout.addWidget(joint_group)
        
        # 執行控制 
        execute_layout = QHBoxLayout()
        
        execute_layout.addWidget(QLabel("移動時間:"))
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 10)
        self.duration_spin.setValue(2)
        self.duration_spin.setSuffix(" 秒")
        execute_layout.addWidget(self.duration_spin)
        
        execute_layout.addStretch()
        
        execute_btn = QPushButton("🎯 執行移動")
        execute_btn.setFixedHeight(35)
        execute_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        execute_btn.clicked.connect(self.execute_manual_move)
        execute_layout.addWidget(execute_btn)
        
        save_pos_btn = QPushButton("💾 保存位置")
        save_pos_btn.setFixedHeight(35)
        save_pos_btn.clicked.connect(self.save_manual_position)
        execute_layout.addWidget(save_pos_btn)
        
        layout.addLayout(execute_layout)
        layout.addStretch()
        
        scroll.setWidget(widget)
        return scroll
    
    def create_position_manager_tab(self):
        """創建位置管理標籤頁"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(5, 5, 5, 5)
        widget.setLayout(layout)
        
        # 位置列表 
        positions_group = QGroupBox("📍 已保存位置")
        positions_group.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
        positions_layout = QVBoxLayout()
        
        self.positions_table = QTableWidget()
        self.positions_table.setColumnCount(3)
        self.positions_table.setHorizontalHeaderLabels(['位置名稱', '關節角度', '操作'])
        
        # 設定列寬
        header = self.positions_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        self.positions_table.setColumnWidth(2, 100)
        
        positions_layout.addWidget(self.positions_table)
        positions_group.setLayout(positions_layout)
        layout.addWidget(positions_group)
        
        # 操作按鈕 
        pos_btn_layout = QHBoxLayout()
        
        refresh_pos_btn = QPushButton("🔄 刷新")
        refresh_pos_btn.setFixedHeight(30)
        refresh_pos_btn.clicked.connect(self.refresh_positions_list)
        pos_btn_layout.addWidget(refresh_pos_btn)
        
        goto_selected_btn = QPushButton("➡️ 前往")
        goto_selected_btn.setFixedHeight(30)
        goto_selected_btn.clicked.connect(self.goto_selected_position)
        pos_btn_layout.addWidget(goto_selected_btn)
        
        delete_pos_btn = QPushButton("🗑️ 刪除")
        delete_pos_btn.setFixedHeight(30)
        delete_pos_btn.clicked.connect(self.delete_selected_position)
        pos_btn_layout.addWidget(delete_pos_btn)
        
        pos_btn_layout.addStretch()
        layout.addLayout(pos_btn_layout)
        
        # 文件操作
        file_btn_layout = QHBoxLayout()
        
        load_positions_btn = QPushButton("📂 載入配置")
        load_positions_btn.setFixedHeight(30)
        load_positions_btn.clicked.connect(self.load_positions_from_file)
        file_btn_layout.addWidget(load_positions_btn)
        
        save_positions_btn = QPushButton("💾 保存配置")
        save_positions_btn.setFixedHeight(30)
        save_positions_btn.clicked.connect(self.save_positions_to_file)
        file_btn_layout.addWidget(save_positions_btn)
        
        file_btn_layout.addStretch()
        layout.addLayout(file_btn_layout)
        
        self.refresh_positions_list()
        return widget
    
    def create_status_tab(self):
        """創建狀態監控標籤頁"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(5, 5, 5, 5)
        widget.setLayout(layout)
        
        # 系統狀態
        status_group = QGroupBox("📊 系統狀態")
        status_group.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
        status_layout = QGridLayout()
        
        self.status_labels = {
            'connection': QLabel("連接狀態: 檢查中..."),
            'hardware': QLabel("硬體狀態: 檢查中..."),
            'movement': QLabel("運動狀態: 停止"),
            'emergency': QLabel("緊急狀態: 正常"),
        }
        
        for i, (key, label) in enumerate(self.status_labels.items()):
            label.setFont(QFont("Microsoft JhengHei", 9))
            status_layout.addWidget(label, i // 2, i % 2)
        
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        # 當前位置
        position_group = QGroupBox("📍 當前位置")
        position_group.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
        position_layout = QVBoxLayout()
        
        self.position_text = QTextEdit()
        self.position_text.setMaximumHeight(120)
        self.position_text.setReadOnly(True)
        self.position_text.setFont(QFont("Consolas", 9))
        position_layout.addWidget(self.position_text)
        
        refresh_btn = QPushButton("🔄 刷新狀態")
        refresh_btn.setFixedHeight(30)
        refresh_btn.clicked.connect(self.update_status_display)
        position_layout.addWidget(refresh_btn)
        
        position_group.setLayout(position_layout)
        layout.addWidget(position_group)
        
        # 校正功能
        calib_group = QGroupBox("🔧 關節校正")
        calib_group.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
        calib_layout = QHBoxLayout()
        
        calib_layout.addWidget(QLabel("選擇關節:"))
        self.calib_combo = QComboBox()
        self.calib_combo.addItems([
            "Joint1 (基座)", "Joint2 (肩部)", "Joint3 (手肘)",
            "Joint4 (腕部俯仰)", "Joint5 (腕部旋轉)", "Joint6 (夾爪)"
        ])
        calib_layout.addWidget(self.calib_combo)
        
        calib_btn = QPushButton("🔧 校正")
        calib_btn.setFixedHeight(30)
        calib_btn.clicked.connect(self.calibrate_joint)
        calib_layout.addWidget(calib_btn)
        
        calib_all_btn = QPushButton("🔧 全部校正")
        calib_all_btn.setFixedHeight(30)
        calib_all_btn.clicked.connect(self.calibrate_all)
        calib_layout.addWidget(calib_all_btn)
        
        calib_group.setLayout(calib_layout)
        layout.addWidget(calib_group)
        
        layout.addStretch()
        return widget
    
    # 控制方法 
    
    def goto_predefined(self, position_name):
        """移動到預定義位置"""
        if not self.check_arm_available():
            return
        
        if self.emergency_stopped:
            self.add_log("⚠️ 緊急停止中，無法執行")
            return
        
        try:
            if position_name == 'home':
                if self.arm_controller:
                    self.arm_controller.close_gripper()
                    time.sleep(0.5)
                    success = self.arm_controller.move_to_home()
                else:
                    success = True
                
                if success:
                    self.add_log(f"✅ 已移動到: {position_name}")
                else:
                    self.add_log(f"❌ 移動失敗: {position_name}")
            else:
                if self.arm_controller:
                    success = self.arm_controller.move_to_predefined(position_name)
                else:
                    success = True
                
                if success:
                    self.add_log(f"✅ 已移動到: {position_name}")
                else:
                    self.add_log(f"❌ 移動失敗: {position_name}")
        except Exception as e:
            self.add_log(f"❌ 錯誤: {e}")
    
    def gripper_control(self, action):
        """夾爪控制"""
        if not self.check_arm_available():
            return
        
        if self.emergency_stopped:
            self.add_log("⚠️ 緊急停止中，無法執行")
            return
        
        try:
            if self.arm_controller:
                if action == 'open':
                    success = self.arm_controller.open_gripper()
                    msg = "打開夾爪"
                else:
                    success = self.arm_controller.close_gripper()
                    msg = "關閉夾爪"
            else:
                success = True
                msg = f"{'打開' if action == 'open' else '關閉'}夾爪 (模擬)"
            
            if success:
                self.add_log(f"✅ {msg}成功")
            else:
                self.add_log(f"❌ {msg}失敗")
        except Exception as e:
            self.add_log(f"❌ 錯誤: {e}")
    
    def execute_sorting_sequence(self, seq_type):
        """執行分類序列"""
        if not self.check_arm_available():
            return

        if self.emergency_stopped:
            self.add_log("⚠️ 緊急停止中，無法執行")
            return

        seq_names = {
            'single': '單一缺陷',
            'double': '兩種缺陷',
            'multiple': '多種缺陷',
            'demo': '演示'
        }

        seq_name = seq_names.get(seq_type, seq_type)
        self.add_log(f"🤖 開始執行【{seq_name}】序列...")

        try:
            success = False

            if not self.is_simulation_mode and self.arm_controller:
                if seq_type in ['single', 'double', 'multiple']:
                    success = self.arm_controller.execute_pick_and_place_sequence(seq_type)
                elif seq_type == 'demo':
                    self.execute_hardware_demo_sequence()
                    success = True
                else:
                    self.add_log(f"❌ 未知序列類型: {seq_type}")
                    return
            else:
                self.execute_simulated_sequence(seq_type)
                success = True

            if success:
                self.action_completed.emit(seq_type, True)
                self.add_log(f"✅ 【{seq_name}】序列完成")
            else:
                self.action_completed.emit(seq_type, False)
                self.add_log(f"❌ 【{seq_name}】序列失敗")

        except Exception as e:
            self.add_log(f"❌ 序列執行錯誤: {e}")
            self.action_completed.emit(seq_type, False)
    
    def execute_hardware_demo_sequence(self):
        """執行演示序列"""
        self.add_log("   📍 步驟1: 移動到原點")
        self.arm_controller.move_to_home()
        time.sleep(1.0)
        
        self.add_log("   📍 步驟2: 測試夾爪")
        self.arm_controller.open_gripper()
        time.sleep(1.0)
        self.arm_controller.close_gripper()
        time.sleep(1.0)
        
        self.add_log("   📍 步驟3: 移動到安全高位")
        self.arm_controller.move_to_predefined('safe_high')
        time.sleep(1.0)
        
        self.add_log("   📍 步驟4: 返回原點")
        self.arm_controller.move_to_home()
    
    def execute_simulated_sequence(self, seq_type):
        """執行模擬序列"""
        seq_names = {
            'single': '單一缺陷',
            'double': '兩種缺陷',
            'multiple': '多種缺陷',
            'demo': '演示'
        }
        
        seq_name = seq_names.get(seq_type, seq_type)
        self.add_log(f"   [模擬] {seq_name}序列執行中...")
        time.sleep(2)
        self.add_log(f"   [模擬] {seq_name}序列完成")
    
    def execute_manual_move(self):
        """執行手動移動"""
        if not self.check_arm_available():
            return
        
        if self.emergency_stopped:
            self.add_log("⚠️ 緊急停止中")
            return
        
        try:
            angles = [self.joint_sliders[f'joint{i+1}'].value() for i in range(6)]
            duration = self.duration_spin.value()
            
            self.add_log(f"🎯 手動移動: {angles}")
            
            if self.arm_controller:
                position = Position.from_list(angles)
                success = self.arm_controller.move_to_position(position, duration)
            else:
                success = True
                self.add_log("   [模擬] 移動執行")
            
            if success:
                self.add_log("✅ 手動移動完成")
            else:
                self.add_log("❌ 手動移動失敗")
        except Exception as e:
            self.add_log(f"❌ 錯誤: {e}")
    
    def get_current_joint_angle(self, joint_id):
        """獲取當前關節角度"""
        if not self.check_arm_available():
            return
        
        if self.arm_controller:
            self.arm_controller.update_current_position()
            angle = getattr(self.arm_controller.current_position, joint_id)
            self.joint_sliders[joint_id].setValue(int(angle))
            self.add_log(f"📍 已獲取 {joint_id}: {angle}°")
        else:
            self.add_log(f"📍 [模擬] {joint_id}")
    
    def set_single_joint(self, joint_id):
        """設置單個關節"""
        if not self.check_arm_available():
            return
        
        if self.emergency_stopped:
            self.add_log("⚠️ 緊急停止中")
            return
        
        joint_index = int(joint_id[-1]) - 1
        angle = self.joint_sliders[joint_id].value()
        
        if self.arm_controller:
            success = self.arm_controller.move_joint(joint_index, angle, 15)
        else:
            success = True
        
        if success:
            self.add_log(f"✅ {joint_id} → {angle}°")
        else:
            self.add_log(f"❌ {joint_id} 失敗")
    
    def save_manual_position(self):
        """保存手動位置"""
        name, ok = QInputDialog.getText(self, '保存位置', '請輸入位置名稱:')
        if ok and name.strip():
            angles = [self.joint_sliders[f'joint{i+1}'].value() for i in range(6)]
            
            if self.arm_controller:
                self.arm_controller.predefined_positions[name.strip()] = Position.from_list(angles)
            
            self.add_log(f"💾 位置已保存: {name.strip()}")
            self.refresh_positions_list()
    
    def emergency_stop(self):
        """緊急停止"""
        self.emergency_stopped = True
        self.emergency_btn.setEnabled(False)
        self.resume_btn.setEnabled(True)
        
        if self.arm_controller:
            self.arm_controller.emergency_stop()
        
        self.add_log("🚨 緊急停止已激活！")
        self.status_labels['emergency'].setText("緊急狀態: 🔴 已停止")
    
    def resume_operation(self):
        """恢復運行"""
        reply = QMessageBox.question(
            self, '確認恢復',
            '確認要恢復系統運行嗎？',
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.emergency_stopped = False
            self.emergency_btn.setEnabled(True)
            self.resume_btn.setEnabled(False)
            
            if self.arm_controller:
                self.arm_controller.resume()
            
            self.add_log("✅ 系統已恢復運行")
            self.status_labels['emergency'].setText("緊急狀態: 🟢 正常")
    
    def calibrate_joint(self):
        """校正單個關節"""
        if not self.check_arm_available():
            return
        
        joint_idx = self.calib_combo.currentIndex()
        joint_name = f"joint{joint_idx + 1}"
        
        self.add_log(f"🔧 開始校正 {joint_name}...")
        
        if self.arm_controller:
            success = self.arm_controller.calibrate_joint(joint_name)
        else:
            success = True
        
        if success:
            self.add_log(f"✅ {joint_name} 校正完成")
        else:
            self.add_log(f"❌ {joint_name} 校正失敗")
    
    def calibrate_all(self):
        """校正所有關節"""
        if not self.check_arm_available():
            return
        
        reply = QMessageBox.question(
            self, '確認校正',
            '確定要校正所有關節嗎？',
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.add_log("🔧 開始校正所有關節...")
            
            if self.arm_controller:
                success = self.arm_controller.calibrate_all_joints()
            else:
                success = True
            
            if success:
                self.add_log("✅ 所有關節校正完成")
            else:
                self.add_log("❌ 關節校正失敗")
    
    def refresh_positions_list(self):
        """刷新位置列表"""
        self.positions_table.setRowCount(0)
        
        if self.arm_controller:
            positions = self.arm_controller.predefined_positions
        else:
            positions = {
                'home': Position(180, 180, 90, 90, 90, 73),
                'safe_high': Position(180, 120, 120, 90, 90, 73),
            }
        
        for i, (name, position) in enumerate(positions.items()):
            self.positions_table.insertRow(i)
            
            name_item = QTableWidgetItem(name)
            self.positions_table.setItem(i, 0, name_item)
            
            angles_str = ', '.join([f"{a:.0f}°" for a in position.to_list()])
            angles_item = QTableWidgetItem(angles_str)
            self.positions_table.setItem(i, 1, angles_item)
            
            btn_widget = QWidget()
            btn_layout = QHBoxLayout()
            btn_layout.setContentsMargins(2, 2, 2, 2)
            
            goto_btn = QPushButton("➡️")
            goto_btn.setFixedSize(30, 25)
            goto_btn.setToolTip("移動")
            goto_btn.clicked.connect(lambda _, n=name: self.goto_predefined(n))
            btn_layout.addWidget(goto_btn)
            
            load_btn = QPushButton("📥")
            load_btn.setFixedSize(30, 25)
            load_btn.setToolTip("載入")
            load_btn.clicked.connect(lambda _, p=position: self.load_position_to_sliders(p))
            btn_layout.addWidget(load_btn)
            
            btn_widget.setLayout(btn_layout)
            self.positions_table.setCellWidget(i, 2, btn_widget)
        
        self.add_log(f"🔄 已刷新 ({len(positions)} 個)")
    
    def load_position_to_sliders(self, position):
        """載入位置到滑桿"""
        angles = position.to_list()
        for i, angle in enumerate(angles):
            self.joint_sliders[f'joint{i+1}'].setValue(int(angle))
        self.add_log(f"📥 位置已載入")
    
    def goto_selected_position(self):
        """移動到選定位置"""
        current_row = self.positions_table.currentRow()
        if current_row < 0:
            self.add_log("⚠️ 請先選擇位置")
            return
        
        position_name = self.positions_table.item(current_row, 0).text()
        self.goto_predefined(position_name)
    
    def delete_selected_position(self):
        """刪除選定位置"""
        current_row = self.positions_table.currentRow()
        if current_row < 0:
            self.add_log("⚠️ 請先選擇位置")
            return
        
        position_name = self.positions_table.item(current_row, 0).text()
        
        system_positions = ['home', 'safe_high', 'check', 'rest']
        if position_name in system_positions:
            QMessageBox.warning(self, "無法刪除", f"'{position_name}' 是系統預設位置")
            return
        
        reply = QMessageBox.question(
            self, '確認刪除',
            f'確定要刪除 "{position_name}" ?',
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if self.arm_controller:
                del self.arm_controller.predefined_positions[position_name]
            
            self.add_log(f"🗑️ 已刪除: {position_name}")
            self.refresh_positions_list()
    
    def load_positions_from_file(self):
        """從文件載入位置"""
        filename, _ = QFileDialog.getOpenFileName(
            self, '載入位置配置', '', 'JSON Files (*.json)'
        )
        
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if self.arm_controller:
                    for name, angles in data.items():
                        self.arm_controller.predefined_positions[name] = Position.from_list(angles)
                
                self.refresh_positions_list()
                self.add_log(f"📂 已載入: {filename}")
                QMessageBox.information(self, '成功', f'已載入 {len(data)} 個位置')
            except Exception as e:
                self.add_log(f"❌ 載入失敗: {e}")
    
    def save_positions_to_file(self):
        """保存位置到文件"""
        filename, _ = QFileDialog.getSaveFileName(
            self, '保存位置配置', 'arm_positions.json', 'JSON Files (*.json)'
        )
        
        if filename:
            try:
                if self.arm_controller:
                    data = {name: pos.to_list() 
                           for name, pos in self.arm_controller.predefined_positions.items()}
                else:
                    data = {}
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                self.add_log(f"💾 已保存: {filename}")
                QMessageBox.information(self, '成功', '配置已保存')
            except Exception as e:
                self.add_log(f"❌ 保存失敗: {e}")
    
    # 輔助方法
    
    def check_arm_available(self):
        """檢查機械手臂是否可用"""
        if self.is_simulation_mode:
            return True
        
        if not self.arm_controller or not self.arm_controller.is_connected:
            self.add_log("⚠️ 機械手臂未連接")
            return False
        return True
    
    def update_joint_label(self, joint_id, value):
        """更新關節標籤"""
        self.joint_labels[joint_id].setText(f"{value}°")
    
    def update_connection_status(self):
        """更新連接狀態"""
        if self.is_simulation_mode:
            status = "🟡 模擬"
            color = "#FF9800"
        elif self.arm_controller and self.arm_controller.is_connected:
            status = f"🟢 {self.arm_controller.port}"
            color = "#4CAF50"
        else:
            status = "🔴 未連接"
            color = "#f44336"
        
        self.connection_label.setText(status)
        self.connection_label.setStyleSheet(f"""
            background-color: {color};
            color: white;
            padding: 4px 10px;
            font-weight: bold;
            border-radius: 3px;
        """)
    
    def update_status_display(self):
        """更新狀態顯示"""
        if self.is_simulation_mode:
            self.status_labels['connection'].setText("連接: 🟡 模擬")
            self.status_labels['hardware'].setText("硬體: 🟡 模擬")
            self.status_labels['movement'].setText("運動: 🟢 就緒")
            
            text = "當前角度（模擬）：\n\n"
            joint_names = ["基座", "肩部", "手肘", "腕俯", "腕旋", "夾爪"]
            for i, name in enumerate(joint_names):
                angle = self.joint_sliders[f'joint{i+1}'].value()
                text += f"{name}: {angle}°\n"
            self.position_text.setPlainText(text)
            return
        
        if not self.arm_controller:
            self.status_labels['connection'].setText("連接: 🔴 未連接")
            self.status_labels['hardware'].setText("硬體: 🔴 不可用")
            self.status_labels['movement'].setText("運動: 🔴 無法控制")
            return
        
        try:
            status = self.arm_controller.get_status()
            
            conn = "🟢 已連接" if status['hardware_available'] else "🔴 未連接"
            self.status_labels['connection'].setText(f"連接: {conn}")
            
            hw = "🟢 正常" if status['hardware_available'] else "🔴 離線"
            self.status_labels['hardware'].setText(f"硬體: {hw}")
            
            mv = "🟡 移動中" if status['is_moving'] else "🟢 停止"
            self.status_labels['movement'].setText(f"運動: {mv}")
            
            joint_info = self.arm_controller.get_joint_info()
            text = "當前角度：\n\n"
            for jid, info in joint_info.items():
                text += f"{info['name']}: {info['current_angle']:.1f}°\n"
            
            self.position_text.setPlainText(text)
            
        except Exception as e:
            self.add_log(f"⚠️ 狀態更新錯誤: {e}")
    
    def start_status_timer(self):
        """啟動狀態更新定時器"""
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status_display)
        self.status_timer.start(2000)
    
    def add_log(self, message):
        """添加日誌"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def darken_color(self, hex_color, factor=0.15):
        """顏色變暗"""
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        r = int(r * (1 - factor))
        g = int(g * (1 - factor))
        b = int(b * (1 - factor))
        return f'#{r:02x}{g:02x}{b:02x}'
    
    def closeEvent(self, event):
        """關閉事件"""
        if not self.is_simulation_mode and self.arm_controller and self.arm_controller.is_connected:
            reply = QMessageBox.question(
                self, '確認關閉',
                '關閉前是否移動到原點？',
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            
            if reply == QMessageBox.Cancel:
                event.ignore()
                return
            elif reply == QMessageBox.Yes:
                try:
                    self.add_log("🏠 正在返回原點...")
                    self.arm_controller.close_gripper()
                    time.sleep(0.5)
                    self.arm_controller.move_to_home()
                    time.sleep(2)
                    self.add_log("✅ 已安全關閉")
                except Exception as e:
                    self.add_log(f"⚠️ 關閉錯誤: {e}")
        
        event.accept()


def main():
    """主函數"""
    from PyQt5.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    font = QFont("Microsoft JhengHei", 9)
    app.setFont(font)
    app.setStyle('Fusion')
    
    print("=" * 60)
    print("🤖 六軸機械手臂控制界面")
    print("=" * 60)
    
    arm_controller = None
    if ARM_AVAILABLE:
        try:
            arm_controller = RoboticArmController()
            if not arm_controller.is_connected:
                print("⚠️ 使用模擬模式")
                arm_controller = None
        except Exception as e:
            print(f"⚠️ 錯誤: {e}")
            arm_controller = None
    
    window = ArmControlWidget(arm_controller=arm_controller)
    window.setWindowTitle("🤖 六軸機械手臂控制面板")
    window.resize(900, 650)
    window.show()
    
    print("\n✅ 界面已啟動")
    if arm_controller:
        print(f"📡 已連接: {arm_controller.port}")
    else:
        print("🟡 模式: 模擬")
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()