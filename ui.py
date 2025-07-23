"""
PCBA 智能檢測控制系統 - UI 介面模組
分離的介面設計元件，提供完整的用戶界面佈局和樣式
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
                            QPushButton, QLabel, QSlider, QTableWidget, 
                            QTableWidgetItem, QGroupBox, QSplitter)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


class PCBAUIInterface:
    """PCBA 檢測系統 UI 介面類"""
    
    def __init__(self, parent):
        self.parent = parent
        self.init_ui_components()
        
    def init_ui_components(self):
        """初始化UI組件"""
        # 設置主窗口屬性
        self.parent.setWindowTitle("PCBA 智能檢測控制系統 v2.0 - 硬體整合版")
        self.parent.setGeometry(100, 100, 1400, 900)
        
        # 創建中央窗口和主佈局
        self.central_widget = QWidget()
        self.parent.setCentralWidget(self.central_widget)
        
        self.main_layout = QHBoxLayout()
        self.central_widget.setLayout(self.main_layout)
        
        # 創建主分割器
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_layout.addWidget(self.main_splitter)
        
        # 創建左右面板
        self.left_panel = self.create_left_panel()
        self.right_panel = self.create_right_panel()
        
        self.main_splitter.addWidget(self.left_panel)
        self.main_splitter.addWidget(self.right_panel)
        
        # 設置分割器比例
        self.main_splitter.setStretchFactor(0, 3)
        self.main_splitter.setStretchFactor(1, 2)
        self.main_splitter.setSizes([840, 560])
        
        # 應用樣式
        self.setup_styles()
        
    def create_left_panel(self):
        """創建左側面板（相機影像和控制面板）"""
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_widget.setLayout(left_layout)
        
        # 相機影像區域
        camera_group = self.create_camera_section()
        left_layout.addWidget(camera_group)
        
        # 控制面板
        control_group = self.create_control_section()
        left_layout.addWidget(control_group)
        
        return left_widget
        
    def create_camera_section(self):
        """創建相機影像區域"""
        camera_group = QGroupBox("📷 相機影像")
        camera_layout = QVBoxLayout()
        
        # 影像顯示標籤
        self.image_display = QLabel("影像即時預覽區")
        self.image_display.setMinimumHeight(400)
        self.image_display.setAlignment(Qt.AlignCenter)
        self.image_display.setStyleSheet("""
            QLabel {
                border: 2px dashed #ccc;
                border-radius: 6px;
                background-color: #f8f9fa;
                font-size: 16px;
                font-weight: bold;
                color: #666;
            }
        """)
        
        camera_layout.addWidget(self.image_display)
        camera_group.setLayout(camera_layout)
        
        return camera_group
        
    def create_control_section(self):
        """創建控制面板區域"""
        control_group = QGroupBox("⚙️ 控制面板")
        control_layout = QVBoxLayout()
        
        # 主要控制按鈕
        button_layout = self.create_main_buttons()
        control_layout.addLayout(button_layout)
        
        # 門檻值控制
        threshold_layout = self.create_threshold_control()
        control_layout.addLayout(threshold_layout)
        
        # 伺服角度控制
        servo_layout = self.create_servo_control()
        control_layout.addLayout(servo_layout)
        
        # 輸送帶速度控制
        speed_layout = self.create_speed_control()
        control_layout.addLayout(speed_layout)
        
        # 系統控制按鈕
        system_layout = self.create_system_buttons()
        control_layout.addLayout(system_layout)
        
        # 繼電器控制
        relay_layout = self.create_relay_control()
        control_layout.addLayout(relay_layout)
        
        control_group.setLayout(control_layout)
        return control_group
        
    def create_main_buttons(self):
        """創建主要控制按鈕"""
        button_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("📷 開始自動檢測")
        self.stop_btn = QPushButton("⛔ 停止")
        self.stop_btn.setEnabled(False)
        
        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.stop_btn)
        
        return button_layout
        
    def create_threshold_control(self):
        """創建門檻值控制"""
        threshold_layout = QHBoxLayout()
        
        threshold_layout.addWidget(QLabel("檢測門檻值:"))
        
        self.threshold_value = QLabel("0.80")
        threshold_layout.addWidget(self.threshold_value)
        
        self.threshold_slider = QSlider(Qt.Horizontal)
        self.threshold_slider.setRange(0, 100)
        self.threshold_slider.setValue(80)
        threshold_layout.addWidget(self.threshold_slider)
        
        return threshold_layout
        
    def create_servo_control(self):
        """創建伺服角度控制"""
        servo_layout = QHBoxLayout()
        
        servo_layout.addWidget(QLabel("伺服馬達角度:"))
        
        self.servo_value = QLabel("90°")
        servo_layout.addWidget(self.servo_value)
        
        self.servo_slider = QSlider(Qt.Horizontal)
        self.servo_slider.setRange(0, 180)
        self.servo_slider.setValue(90)
        servo_layout.addWidget(self.servo_slider)
        
        return servo_layout
        
    def create_speed_control(self):
        """創建輸送帶速度控制"""
        speed_layout = QHBoxLayout()
        
        speed_layout.addWidget(QLabel("輸送帶速度:"))
        
        self.speed_value = QLabel("50%")
        speed_layout.addWidget(self.speed_value)
        
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(0, 100)
        self.speed_slider.setValue(50)
        speed_layout.addWidget(self.speed_slider)
        
        return speed_layout
        
    def create_system_buttons(self):
        """創建系統控制按鈕"""
        system_layout = QHBoxLayout()
        
        self.conveyor_btn = QPushButton("▶️ 啟動輸送帶")
        self.reset_btn = QPushButton("🔄 重設系統")
        
        system_layout.addWidget(self.conveyor_btn)
        system_layout.addWidget(self.reset_btn)
        
        return system_layout
        
    def create_relay_control(self):
        """創建繼電器控制"""
        relay_layout = QHBoxLayout()
        
        self.relay_btn = QPushButton("🔌 繼電器開關")
        self.relay_status = QLabel("繼電器狀態：🔴 關閉")
        
        relay_layout.addWidget(self.relay_btn)
        relay_layout.addWidget(self.relay_status)
        
        return relay_layout
        
    def create_right_panel(self):
        """創建右側面板（狀態監控和今日記錄）"""
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_widget.setLayout(right_layout)
        
        # 創建垂直分割器
        self.right_splitter = QSplitter(Qt.Vertical)
        right_layout.addWidget(self.right_splitter)
        
        # 狀態監控區域
        status_widget = self.create_status_section()
        self.right_splitter.addWidget(status_widget)
        
        # 今日記錄區域
        log_widget = self.create_log_section()
        self.right_splitter.addWidget(log_widget)
        
        # 設置分割器比例
        self.right_splitter.setStretchFactor(0, 1)
        self.right_splitter.setStretchFactor(1, 1)
        self.right_splitter.setSizes([400, 400])
        
        return right_widget
        
    def create_status_section(self):
        """創建狀態監控區域"""
        status_group = QGroupBox("📊 狀態監控")
        status_layout = QVBoxLayout()
        
        # 系統狀態顯示
        self.create_system_status_labels(status_layout)
        
        # 生產統計
        self.create_production_stats(status_layout)
        
        # 缺陷分析
        self.create_defect_analysis(status_layout)
        
        # 快速操作按鈕
        self.create_quick_actions(status_layout)
        
        status_layout.addStretch()
        status_group.setLayout(status_layout)
        
        return status_group
        
    def create_system_status_labels(self, parent_layout):
        """創建系統狀態標籤"""
        # 系統狀態標籤
        self.system_status = QLabel("系統狀態：🔴 停止")
        self.conveyor_status = QLabel("輸送帶狀態：🔴 停止")
        self.servo_status = QLabel("伺服控制：🟢 就緒 (90°)")
        self.sensor_status = QLabel("光電感測器：🟢 正常")
        
        # 根據硬體狀態設置相機狀態
        camera_status_text = "相機狀態：🟢 正常" if hasattr(self.parent, 'hardware') and self.parent.hardware.camera else "相機狀態：🔴 離線"
        self.camera_status = QLabel(camera_status_text)
        
        parent_layout.addWidget(self.system_status)
        parent_layout.addWidget(self.conveyor_status)
        parent_layout.addWidget(self.servo_status)
        parent_layout.addWidget(self.sensor_status)
        parent_layout.addWidget(self.camera_status)
        
    def create_production_stats(self, parent_layout):
        """創建生產統計區域"""
        stats_label = QLabel("生產統計")
        stats_label.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
        parent_layout.addWidget(stats_label)
        
        stats_widget = QWidget()
        stats_layout = QGridLayout()
        
        self.total_label = QLabel("總檢測數：0")
        self.pass_label = QLabel("合格數：0")
        self.defect_label = QLabel("缺陷數：0")
        self.pass_rate_label = QLabel("合格率：0.0%")
        
        stats_layout.addWidget(self.total_label, 0, 0)
        stats_layout.addWidget(self.pass_label, 0, 1)
        stats_layout.addWidget(self.defect_label, 1, 0)
        stats_layout.addWidget(self.pass_rate_label, 1, 1)
        
        stats_widget.setLayout(stats_layout)
        parent_layout.addWidget(stats_widget)
        
    def create_defect_analysis(self, parent_layout):
        """創建缺陷分析區域"""
        defect_label = QLabel("缺陷分析")
        defect_label.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
        parent_layout.addWidget(defect_label)
        
        defect_widget = QWidget()
        defect_layout = QGridLayout()
        
        self.short_label = QLabel("短路: 0")
        self.open_label = QLabel("斷路: 0")
        self.bridge_label = QLabel("橋接: 0")
        self.missing_label = QLabel("缺件: 0")
        
        defect_layout.addWidget(self.short_label, 0, 0)
        defect_layout.addWidget(self.open_label, 0, 1)
        defect_layout.addWidget(self.bridge_label, 1, 0)
        defect_layout.addWidget(self.missing_label, 1, 1)
        
        defect_widget.setLayout(defect_layout)
        parent_layout.addWidget(defect_widget)
        
    def create_quick_actions(self, parent_layout):
        """創建快速操作區域"""
        quick_label = QLabel("快速操作")
        quick_label.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
        parent_layout.addWidget(quick_label)
        
        quick_layout = QHBoxLayout()
        
        self.export_btn = QPushButton("📤 匯出報告")
        self.clear_btn = QPushButton("🗑️ 清除記錄")
        
        quick_layout.addWidget(self.export_btn)
        quick_layout.addWidget(self.clear_btn)
        
        parent_layout.addLayout(quick_layout)
        
    def create_log_section(self):
        """創建今日記錄區域"""
        log_group = QGroupBox("🧾 今日記錄")
        log_layout = QVBoxLayout()
        
        # 創建記錄表格
        self.log_table = QTableWidget()
        self.log_table.setColumnCount(4)
        self.log_table.setHorizontalHeaderLabels(["時間", "結果", "缺陷", "動作"])
        
        # 設置表格屬性
        self.setup_log_table()
        
        log_layout.addWidget(self.log_table)
        log_group.setLayout(log_layout)
        
        return log_group
        
    def setup_log_table(self):
        """設置記錄表格屬性"""
        self.log_table.setAlternatingRowColors(True)
        self.log_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.log_table.resizeColumnsToContents()
        self.log_table.horizontalHeader().setStretchLastSection(True)
        
    def setup_styles(self):
        """設置界面樣式"""
        self.parent.setStyleSheet("""
            QMainWindow {
                background-color: #f8f9fa;
            }
            
            QGroupBox {
                font-weight: bold;
                border: 2px solid #4CAF50;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
                background-color: white;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #333;
            }
            
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                min-height: 20px;
            }
            
            QPushButton:hover {
                background-color: #45a049;
            }
            
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            
            QLabel {
                color: #333;
                font-size: 12px;
                padding: 2px;
            }
            
            QSlider::groove:horizontal {
                border: 1px solid #bbb;
                background: white;
                height: 10px;
                border-radius: 4px;
            }
            
            QSlider::handle:horizontal {
                background: #4CAF50;
                border: 1px solid #5c5c5c;
                width: 18px;
                margin: -2px 0;
                border-radius: 3px;
            }
            
            QTableWidget {
                gridline-color: #ddd;
                background-color: white;
            }
            
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #eee;
            }
            
            QTableWidget::item:selected {
                background-color: #e3f2fd;
            }
            
            QTableWidget QHeaderView::section {
                background-color: #4CAF50;
                color: white;
                padding: 8px;
                border: none;
                font-weight: bold;
            }
        """)
        
    def connect_signals(self, controller):
        """連接信號到控制器方法"""
        # 主要控制按鈕
        self.start_btn.clicked.connect(controller.start_auto_detection)
        self.stop_btn.clicked.connect(controller.stop_auto_detection)
        
        # 滑桿控制
        self.threshold_slider.valueChanged.connect(controller.update_threshold)
        self.servo_slider.valueChanged.connect(controller.update_servo)
        self.speed_slider.valueChanged.connect(controller.update_conveyor_speed)
        
        # 系統控制按鈕
        self.conveyor_btn.clicked.connect(controller.toggle_conveyor)
        self.reset_btn.clicked.connect(controller.reset_system)
        self.relay_btn.clicked.connect(controller.toggle_relay)
        
        # 快速操作按鈕
        self.export_btn.clicked.connect(controller.export_report)
        self.clear_btn.clicked.connect(controller.clear_records)
        
    def get_ui_components(self):
        """返回所有UI組件的字典，供主程序使用"""
        return {
            # 顯示組件
            'image_display': self.image_display,
            'system_status': self.system_status,
            'conveyor_status': self.conveyor_status,
            'servo_status': self.servo_status,
            'sensor_status': self.sensor_status,
            'camera_status': self.camera_status,
            'relay_status': self.relay_status,
            
            # 控制組件
            'start_btn': self.start_btn,
            'stop_btn': self.stop_btn,
            'conveyor_btn': self.conveyor_btn,
            'reset_btn': self.reset_btn,
            'relay_btn': self.relay_btn,
            'export_btn': self.export_btn,
            'clear_btn': self.clear_btn,
            
            # 滑桿和數值顯示
            'threshold_slider': self.threshold_slider,
            'threshold_value': self.threshold_value,
            'servo_slider': self.servo_slider,
            'servo_value': self.servo_value,
            'speed_slider': self.speed_slider,
            'speed_value': self.speed_value,
            
            # 統計標籤
            'total_label': self.total_label,
            'pass_label': self.pass_label,
            'defect_label': self.defect_label,
            'pass_rate_label': self.pass_rate_label,
            'short_label': self.short_label,
            'open_label': self.open_label,
            'bridge_label': self.bridge_label,
            'missing_label': self.missing_label,
            
            # 表格
            'log_table': self.log_table
        }


class UIStyleManager:
    """UI 樣式管理器"""
    
    @staticmethod
    def get_button_style(color="#4CAF50"):
        """獲取按鈕樣式"""
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                min-height: 20px;
            }}
            QPushButton:hover {{
                background-color: {UIStyleManager.darken_color(color)};
            }}
            QPushButton:pressed {{
                background-color: {UIStyleManager.darken_color(color, 0.8)};
            }}
            QPushButton:disabled {{
                background-color: #cccccc;
                color: #666666;
            }}
        """
    
    @staticmethod
    def darken_color(hex_color, factor=0.9):
        """將顏色變暗"""
        hex_color = hex_color.lstrip('#')
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        darkened = tuple(int(c * factor) for c in rgb)
        return f"#{darkened[0]:02x}{darkened[1]:02x}{darkened[2]:02x}"
    
    @staticmethod
    def get_status_colors():
        """獲取狀態顏色"""
        return {
            'running': '#4CAF50',    # 綠色
            'stopped': '#f44336',    # 紅色
            'warning': '#ff9800',    # 橙色
            'normal': '#2196f3'      # 藍色
        }


# 使用範例
if __name__ == "__main__":
    """
    這個模組應該被主程序導入使用，不應該單獨運行
    但這裡提供一個簡單的測試範例
    """
    import sys
    from PyQt5.QtWidgets import QApplication, QMainWindow
    
    class TestWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.ui = PCBAUIInterface(self)
            
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec_())