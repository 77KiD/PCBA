"""
PCB檢測系統 - 完整版
檢測項目: 鼠咬、斷路、雜銅
包含六軸機械手臂控制功能
"""

# 環境配置
JETSON_ENV = False  # 設為 True 如果在 Jetson 上運行

import sys
import os
import cv2
import time
import numpy as np
import serial
import serial, time
import serial.tools.list_ports
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QGridLayout, QPushButton, QLabel, 
                            QSlider, QTableWidget, QTableWidgetItem, QGroupBox,
                            QFrame, QScrollArea, QSplitter, QMessageBox, QFileDialog,
                            QSpinBox, QTabWidget, QTextEdit, QComboBox, QHeaderView,
                            QDoubleSpinBox, QCheckBox, QInputDialog)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot
from PyQt5.QtGui import QFont, QPalette, QColor, QPixmap, QPainter, QImage

# 導入自定義模組
from hardware_controller import HardwareController
from detection_engine import DetectionThread, CameraThread
from data_manager import DataManager
from image_processor import ImageProcessor
from arm_control_ui import ArmControlWidget as OldArmControlWidget
from serial.tools import list_ports

# 嘗試導入機械手臂控制器
try:
    from robotic_arm_controller import RoboticArmController, Position
    ARM_CONTROLLER_AVAILABLE = True
except ImportError:
    ARM_CONTROLLER_AVAILABLE = False
    print("⚠️ 機械手臂控制模組未找到，將使用基本控制")

# 嘗試導入配置管理器
try:
    from config_manager import ConfigManager, HardwareConfig, DetectionConfig
    CONFIG_MANAGER_AVAILABLE = True
except ImportError:
    CONFIG_MANAGER_AVAILABLE = False
    print("⚠️ 配置管理模組未找到")
ir_port = None
arm_port = None
others = []



# 自動 COM Port 分配函數
def auto_assign_com_ports():
    print("\n" + "="*70)
    print("  🔍 自動分配 COM Ports")
    print("="*70)

    ports = list(list_ports.comports())
    if not ports:
        print("❌ 未找到任何 COM port")
        print("="*70 + "\n")
        return None, None

    print(f"✅ 找到 {len(ports)} 個 COM port:\n")

    arduino_candidates = []
    arm_candidates = []
    other_ports = []

    # 基礎列印 + 分類候選
    for p in ports:
        desc = p.description or ""
        manu = p.manufacturer or ""
        hwid = p.hwid or ""

        print(f"📍 {p.device}")
        print(f"   描述: {desc}")
        print(f"   製造商: {manu}")

        u_desc = (p.description or "").upper()
        u_manu = (p.manufacturer or "").upper()
        u_hwid = (p.hwid or "").upper()

        # IR Arduino 嚴格規則：只接受 CH340 / WCH / 1A86:7523
        is_ir_arduino = (
            ("CH340" in u_desc) or
            ("USB-SERIAL CH340" in u_desc) or
            ("WCH.CN" in u_manu) or
            (("1A86" in u_hwid) and ("7523" in u_hwid))
        )

        if is_ir_arduino:
            arduino_candidates.append(p.device)
            print("   🎯 識別為: Arduino (IR控制)")
        else:
            other_ports.append(p.device)
            print("   ℹ️  未明確識別 (USB 轉串口裝置)")
        print()

    print("-"*70)

    arduino_port = None
    arm_port = None

    # 1: 找到明確的 Arduino
    if arduino_candidates:
        arduino_port = arduino_candidates[0]
        print(f"✅ Arduino (IR控制) → {arduino_port}")
        if len(arduino_candidates) > 1:
            print("   ℹ️  發現多個 Arduino，使用第一個")

    # 2: 找到明確的機械手臂
    if arm_candidates:
        arm_port = arm_candidates[0]
        print(f"✅ 機械手臂 → {arm_port}")
        if len(arm_candidates) > 1:
            print("   ℹ️  發現多個可能的機械手臂，使用第一個")

    # 3: 只找到一種裝置，需要分配另一個
    if arduino_port and not arm_port:
        if other_ports:
            arm_port = other_ports[0]
            print(f"⚠️  機械手臂 → {arm_port} (根據剩餘 port 推測)")
        elif len(ports) > 1:
            for p in ports:
                if p.device != arduino_port:
                    arm_port = p.device
                    print(f"⚠️  機械手臂 → {arm_port} (使用第二個可用 port)")
                    break

        if not arm_port:
            arm_port = arduino_port
            print("⚠️  只有一個 COM port!")
            print(f"   Arduino 和機械手臂共用: {arm_port}")
            print("   ⚡ 警告: 這可能導致通訊衝突!")

    elif arm_port and not arduino_port:
        if other_ports:
            arduino_port = other_ports[0]
            print(f"⚠️  Arduino (IR控制) → {arduino_port} (根據剩餘 port 推測)")
        elif len(ports) > 1:
            for p in ports:
                if p.device != arm_port:
                    arduino_port = p.device
                    print(f"⚠️  Arduino (IR控制) → {arduino_port} (使用第二個可用 port)")
                    break

        if not arduino_port:
            arduino_port = arm_port
            print("⚠️  只有一個 COM port!")
            print(f"   Arduino 和機械手臂共用: {arduino_port}")
            print("   ⚡ 警告: 這可能導致通訊衝突!")

    # 4: 都沒找到明確裝置，使用預設分配
    elif not arduino_port and not arm_port:
        if len(ports) >= 2:
            arduino_port = ports[0].device
            arm_port = ports[1].device
            print("⚠️  無法自動識別裝置類型，使用預設分配:")
            print(f"   Arduino (IR控制) → {arduino_port}")
            print(f"   機械手臂 → {arm_port}")
            print("💡 如果分配錯誤，請檢查裝置管理員或手動修改程式")
        elif len(ports) == 1:
            arduino_port = arm_port = ports[0].device
            print(f"⚠️  只有一個 COM port: {arduino_port}")
            print("   Arduino 和機械手臂將共用此 port")
            print("   ⚡ 警告: 這會導致通訊衝突!")

    print("="*70 + "\n")

    # 驗證
    if not arduino_port or not arm_port:
        print("❌ COM Port 分配失敗")
        return None, None

    return arduino_port, arm_port


def _probe_ident(port: str, baud: int = 115200, timeout: float = 0.3) -> str:
    try:
        with serial.Serial(port, baudrate=baud, timeout=timeout) as ser:
            time.sleep(1.2)

            ser.reset_input_buffer()
            ser.write(b"IDENT\n")
            ser.flush()

            chunks = []
            t0 = time.time()
            while time.time() - t0 < 1.2:
                data = ser.read(256)
                if data:
                    chunks.append(data)
                time.sleep(0.05)

            resp = b"".join(chunks).decode(errors="ignore").strip()
            return resp
    except Exception:
        return ""


def auto_assign_com_ports_safely():
    """
    回傳: (ir_port, arm_port, dbg)
    """
    dbg = []
    ir_port = None
    arm_port = None
    others = []

    print("  [自動分配] 開始掃描 COM ports...")

    # 1 列出所有 ports
    try:
        from serial.tools import list_ports
        ports = list(list_ports.comports())
        print(f"  [自動分配] 找到 {len(ports)} 個 COM ports")
    except Exception as e:
        dbg.append(f"[AUTO] list_ports failed: {e}")
        print(f"  [自動分配] 錯誤: {e}")
        return None, None, dbg

    if not ports:
        dbg.append("[AUTO] No COM ports found.")
        print("  [自動分配] 未找到任何 COM ports")
        return None, None, dbg

    # 過濾掉藍牙裝置
    def is_bluetooth(p):
        """判斷是否為藍牙裝置"""
        desc = (p.description or "").lower()
        hwid = (p.hwid or "").lower()
        manu = (p.manufacturer or "").lower()
        
        return any([
            "bluetooth" in desc,
            "藍牙" in desc or "藍芽" in desc,
            "bthenum" in hwid,
            "bluetooth" in manu
        ])
    
    # 過濾掉藍牙 ports
    filtered_ports = [p for p in ports if not is_bluetooth(p)]
    bluetooth_count = len(ports) - len(filtered_ports)
    
    if bluetooth_count > 0:
        print(f"  [自動分配] 已過濾 {bluetooth_count} 個藍牙裝置")
        dbg.append(f"[AUTO] Filtered {bluetooth_count} bluetooth devices")
    
    if not filtered_ports:
        print("  [自動分配] 過濾後沒有可用的 COM ports")
        return None, None, dbg
    
    ports = filtered_ports  # 使用過濾後的 ports

    # 2) 用 desc/manu/hwid 做初步猜測
    def score_port(p):
        desc = (p.description or "").lower()
        manu = (p.manufacturer or "").lower()
        hwid = (p.hwid or "").lower()

        score = 0
        # CH340 晶片 
        if "ch340" in desc or "ch340" in hwid:
            score += 50
        if "1a86:7523" in hwid:
            score += 60  # 提高 CH340 的權重
        # Arduino 官方板
        if "arduino" in desc or "arduino" in manu:
            score += 30
        # USB 轉串口
        if "usb-serial" in desc or "usb serial" in desc:
            score += 10
        # FTDI 晶片
        if "ftdi" in manu or "0403:6001" in hwid:
            score += 20
        
        return score

    ranked = sorted(ports, key=score_port, reverse=True)

    dbg.append(f"[AUTO] Found {len(ports)} ports (after filtering): {[p.device for p in ports]}")
    
    # 顯示每個 port 的詳細資訊
    for i, p in enumerate(ports):
        score = score_port(p)
        print(f"  [{i+1}] {p.device}")
        print(f"      描述: {p.description}")
        print(f"      製造商: {p.manufacturer or 'N/A'}")
        print(f"      評分: {score}")
        dbg.append(f"[AUTO] {p.device} desc={p.description} score={score}")

    # 3) 預先挑最高分當 ir_port 候選
    if ranked:
        ir_port = ranked[0].device
        dbg.append(f"[AUTO] Candidate IR port (by score): {ir_port}")
        print(f"  [自動分配] IR 候選: {ir_port}")

    # 4) others
    others = [p.device for p in ranked[1:]] if len(ranked) > 1 else []

    # 5) probe：嘗試 IDENT/PING 來確認 IR / ARM 
    import time
    import threading
    
    try:
        import serial
    except Exception as e:
        dbg.append(f"[AUTO] pyserial not available: {e}")
        print(f"  [自動分配] pyserial 不可用: {e}")
        return ir_port, (others[0] if others else None), dbg

    def probe_with_timeout(dev, timeout=1.5):
        """帶超時保護的 probe - 使用 threading"""
        result = {"dev": dev, "ok": False, "text": "timeout"}
        
        def do_probe():
            try:
                ser = serial.Serial(dev, 115200, timeout=0.2)
                time.sleep(0.3)  # 縮短等待時間
                
                try:
                    ser.reset_input_buffer()
                except:
                    pass

                resp_all = ""
                for cmd in ("IDENT", "PING"):  # 只測試 2 個命令
                    try:
                        ser.write((cmd + "\n").encode("utf-8"))
                        time.sleep(0.1)
                        resp = ser.read(1000).decode("utf-8", errors="ignore").strip()
                        if resp:
                            resp_all += (resp + "\n")
                    except:
                        pass

                try:
                    ser.close()
                except:
                    pass

                result["ok"] = True
                result["text"] = resp_all.strip()
                
            except Exception as e:
                result["ok"] = False
                result["text"] = str(e)
        
        # 在獨立線程中執行 probe
        thread = threading.Thread(target=do_probe)
        thread.daemon = True
        thread.start()
        thread.join(timeout=timeout)  # 最多等待 1.5 秒
        
        if thread.is_alive():
            result["ok"] = False
            result["text"] = "timeout"
            print(f"(超時)")
        
        return result

    def looks_like_ir(text: str):
        t = (text or "").lower()
        keys = ["ir", "sensor", "conv", "conveyor", "relay", "uno", "arduino ir"]
        return any(k in t for k in keys)

    def looks_like_arm(text: str):
        t = (text or "").lower()
        keys = ["arm", "robot", "servo", "sequence", "seq"]
        return any(k in t for k in keys)

    # 建立要 probe 的清單
    probe_list = []
    for d in ([ir_port] + others):
        if d and d not in probe_list:
            probe_list.append(d)

    dbg.append(f"[AUTO] Probe list: {probe_list}")
    print(f"  [自動分配] 開始探測 {len(probe_list)} 個 ports...")

    results = []
    for dev in probe_list:
        print(f"    [Probe] 測試 {dev}...", end=" ", flush=True)
        r = probe_with_timeout(dev, timeout=1.5)
        results.append(r)
        
        if r["ok"]:
            print(f"✅ (回應: {r['text'][:40]}...)")
        else:
            print(f"❌ ({r['text'][:30]})")
        
    for r in results:
        if r["ok"]:
            dbg.append(f"[AUTO] Probe {r['dev']} OK, text='{r['text'][:120]}'")
        else:
            dbg.append(f"[AUTO] Probe {r['dev']} FAIL: {r['text']}")

    # 6) 根據回應內容判斷
    ir_candidates = [r["dev"] for r in results if r["ok"] and looks_like_ir(r["text"])]
    arm_candidates = [r["dev"] for r in results if r["ok"] and looks_like_arm(r["text"])]

    # 7) 決策邏輯
    if ir_candidates:
        ir_port = ir_candidates[0]
        print(f"  [自動分配] ✅ IR port 確認: {ir_port}")
    elif ir_port:
        print(f"  [自動分配] ⚠️ IR port (預設): {ir_port}")

    if arm_candidates:
        for d in arm_candidates:
            if d != ir_port:
                arm_port = d
                break
        if arm_port:
            print(f"  [自動分配] ✅ ARM port 確認: {arm_port}")
    
    # Fallback: 用剩下的第一個 port
    if arm_port is None:
        ok_ports = [r["dev"] for r in results if r["ok"]]
        for d in ok_ports:
            if d != ir_port:
                arm_port = d
                print(f"  [自動分配] ⚠️ ARM port (fallback): {arm_port}")
                break

    print(f"  [自動分配] 最終結果: IR={ir_port}, ARM={arm_port}")
    dbg.append(f"[AUTO] Result => IR={ir_port}, ARM={arm_port}")
    
    return ir_port, arm_port, dbg


class ArmControlWidget(QWidget):
    """機械手臂控制界面 - 獨立窗口"""
    
    # 動作完成
    action_completed = pyqtSignal(str, bool)  # (target, success)
    
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
        
        # 如果是模擬模式，顯示警告
        if self.is_simulation_mode:
            self.add_log("⚠️ 模擬模式：機械手臂未連接，所有操作僅在界面模擬")
        else:
            self.add_log("✅ 機械手臂控制界面已就緒")
    
    def init_ui(self):
        """初始化用戶界面"""
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        
        # 標題欄
        title_layout = QHBoxLayout()
        
        title_label = QLabel("🤖 六軸機械手臂控制面板")
        title_label.setFont(QFont("Microsoft JhengHei", 14, QFont.Bold))
        title_label.setStyleSheet("color: #2196F3; padding: 5px;")
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        # 連接狀態
        self.connection_label = QLabel()
        self.update_connection_status()
        title_layout.addWidget(self.connection_label)
        
        main_layout.addLayout(title_layout)
        
        # 緊急停止控制
        emergency_layout = QHBoxLayout()
        
        self.emergency_btn = QPushButton("🚨 緊急停止")
        self.emergency_btn.setMinimumHeight(50)
        self.emergency_btn.setStyleSheet(
            "background-color: #FF5722; color: white; font-weight: bold; font-size: 14px;"
        )
        self.emergency_btn.clicked.connect(self.emergency_stop)
        emergency_layout.addWidget(self.emergency_btn, 2)
        
        self.resume_btn = QPushButton("▶️ 恢復運行")
        self.resume_btn.setMinimumHeight(50)
        self.resume_btn.setStyleSheet(
            "background-color: #009688; color: white; font-weight: bold; font-size: 14px;"
        )
        self.resume_btn.clicked.connect(self.resume_operation)
        self.resume_btn.setEnabled(False)
        emergency_layout.addWidget(self.resume_btn, 1)
        
        main_layout.addLayout(emergency_layout)
        
        # ⚠️ 關鍵修復:先創建日誌文本框,以便其他組件可以使用 add_log()
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(120)
        self.log_text.setReadOnly(True)
        
        # 標籤頁 (現在可以安全地調用 add_log 了)
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)
        
        tab_widget.addTab(self.create_quick_control_tab(), "⚡ 快速控制")
        tab_widget.addTab(self.create_manual_control_tab(), "🔧 手動控制")
        tab_widget.addTab(self.create_position_manager_tab(), "📍 位置管理")
        tab_widget.addTab(self.create_status_tab(), "📊 狀態監控")
        
        # 日誌區域 
        log_group = QGroupBox("📝 操作日誌")
        log_layout = QVBoxLayout()
        
        log_layout.addWidget(self.log_text)
        
        log_btn_layout = QHBoxLayout()
        clear_log_btn = QPushButton("🗑️ 清除日誌")
        clear_log_btn.clicked.connect(lambda: self.log_text.clear())
        log_btn_layout.addWidget(clear_log_btn)
        log_btn_layout.addStretch()
        
        log_layout.addLayout(log_btn_layout)
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)

    def create_quick_control_tab(self):
        """創建快速控制標籤頁"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # 快速位置
        quick_pos_group = QGroupBox("📍 快速位置")
        quick_pos_layout = QGridLayout()
        
        # 在快速位置中新增三分類區域按鈕
        quick_positions = [
            ("🏠 原點位置", lambda: self.goto_predefined('home'), 0, 0, "#2196F3"),
            ("☁️ 安全高位", lambda: self.goto_predefined('safe_high'), 0, 1, "#9C27B0"),
            ("🔍 檢查位置", lambda: self.goto_predefined('check'), 1, 0, "#FF9800"),
            ("😴 休息位置", lambda: self.goto_predefined('rest'), 1, 1, "#607D8B"),
            
            # 新增三分類區域快速位置
            ("🔵 單一缺陷區", lambda: self.goto_predefined('single_defect_area'), 2, 0, "#2196F3"),
            ("🟡 兩種缺陷區", lambda: self.goto_predefined('double_defect_area'), 2, 1, "#FF9800"),
            ("🔴 多種缺陷區", lambda: self.goto_predefined('multiple_defect_area'), 3, 0, "#f44336"),
        ]
        
        for text, func, row, col, color in quick_positions:
            btn = QPushButton(text)
            btn.setMinimumHeight(60)
            btn.setFont(QFont("Microsoft JhengHei", 11, QFont.Bold))
            btn.setStyleSheet(f"background-color: {color}; color: white;")
            btn.clicked.connect(func)
            quick_pos_layout.addWidget(btn, row, col)
        
        quick_pos_group.setLayout(quick_pos_layout)
        layout.addWidget(quick_pos_group)
        
        # 夾爪控制
        gripper_group = QGroupBox("✋ 夾爪控制")
        gripper_layout = QHBoxLayout()
        
        open_gripper_btn = QPushButton("🔓 打開夾爪 (73°)")
        open_gripper_btn.setMinimumHeight(60)
        open_gripper_btn.setFont(QFont("Microsoft JhengHei", 12, QFont.Bold))
        open_gripper_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        open_gripper_btn.clicked.connect(lambda: self.gripper_control('open'))
        gripper_layout.addWidget(open_gripper_btn)
        
        close_gripper_btn = QPushButton("🔒 關閉夾爪 (30°)")
        close_gripper_btn.setMinimumHeight(60)
        close_gripper_btn.setFont(QFont("Microsoft JhengHei", 12, QFont.Bold))
        close_gripper_btn.setStyleSheet("background-color: #f44336; color: white;")
        close_gripper_btn.clicked.connect(lambda: self.gripper_control('close'))
        gripper_layout.addWidget(close_gripper_btn)
        
        gripper_group.setLayout(gripper_layout)
        layout.addWidget(gripper_group)
        
        # 自動分類序列 
        sorting_group = QGroupBox("🤖 三分類自動序列")
        sorting_layout = QGridLayout()

        # 第一行單一缺陷
        single_btn = QPushButton("🔵 單一缺陷分類")
        single_btn.setMinimumHeight(60)
        single_btn.setFont(QFont("Microsoft JhengHei", 12, QFont.Bold))
        single_btn.setStyleSheet("background-color: #2196F3; color: white;")
        single_btn.clicked.connect(lambda: self.execute_sorting_sequence('single'))
        sorting_layout.addWidget(single_btn, 0, 0, 1, 2)

        # 第二行兩種缺陷
        double_btn = QPushButton("🟡 兩種缺陷分類")
        double_btn.setMinimumHeight(60)
        double_btn.setFont(QFont("Microsoft JhengHei", 12, QFont.Bold))
        double_btn.setStyleSheet("background-color: #FF9800; color: white;")
        double_btn.clicked.connect(lambda: self.execute_sorting_sequence('double'))
        sorting_layout.addWidget(double_btn, 1, 0, 1, 2)

        # 第三行多種缺陷
        multiple_btn = QPushButton("🔴 多種缺陷分類")
        multiple_btn.setMinimumHeight(60)
        multiple_btn.setFont(QFont("Microsoft JhengHei", 12, QFont.Bold))
        multiple_btn.setStyleSheet("background-color: #f44336; color: white;")
        multiple_btn.clicked.connect(lambda: self.execute_sorting_sequence('multiple'))
        sorting_layout.addWidget(multiple_btn, 2, 0, 1, 2)

        # 第四行演示序列
        demo_btn = QPushButton("🎬 執行演示序列")
        demo_btn.setMinimumHeight(50)
        demo_btn.setFont(QFont("Microsoft JhengHei", 11, QFont.Bold))
        demo_btn.setStyleSheet("background-color: #9C27B0; color: white;")
        demo_btn.clicked.connect(lambda: self.execute_sorting_sequence('demo'))
        sorting_layout.addWidget(demo_btn, 3, 0, 1, 2)

        sorting_group.setLayout(sorting_layout)
        layout.addWidget(sorting_group)

        # 說明文字
        info_label = QLabel(
            "💡 三分類說明:\n"
            "🔵 單一缺陷：檢測到1種缺陷 → 區域1\n"
            "🟡 兩種缺陷：檢測到2種缺陷 → 區域2\n"
            "🔴 多種缺陷：檢測到3種及以上缺陷 → 區域3"
        )
        info_label.setStyleSheet(
            "color: #666; font-size: 10px; padding: 10px; "
            "background-color: #f5f5f5; border-radius: 5px;"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        layout.addStretch()
        return widget
    
    def create_manual_control_tab(self):
        """創建手動控制標籤頁"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # 關節控制
        joint_group = QGroupBox("🔧 關節角度控制")
        joint_layout = QGridLayout()
        
        self.joint_sliders = {}
        self.joint_labels = {}
        
        joints = [
            ("joint1", "基座旋轉", 0, 180, 180),
            ("joint2", "肩部俯仰", 0, 180, 180),
            ("joint3", "手肘彎曲", 0, 180, 90),
            ("joint4", "腕部俯仰", 0, 180, 90),
            ("joint5", "腕部旋轉", 0, 180, 90),
            ("joint6", "夾爪", 30, 73, 73),
        ]
        
        for i, (jid, name, min_v, max_v, default) in enumerate(joints):
            # 名稱標籤
            label = QLabel(name)
            label.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
            joint_layout.addWidget(label, i, 0)
            
            # 角度顯示
            angle_label = QLabel(f"{default}°")
            angle_label.setMinimumWidth(50)
            angle_label.setAlignment(Qt.AlignCenter)
            self.joint_labels[jid] = angle_label
            joint_layout.addWidget(angle_label, i, 1)
            
            # 滑桿
            slider = QSlider(Qt.Horizontal)
            slider.setRange(min_v, max_v)
            slider.setValue(default)
            slider.valueChanged.connect(lambda v, j=jid: self.update_joint_label(j, v))
            self.joint_sliders[jid] = slider
            joint_layout.addWidget(slider, i, 2)
            
            # 快捷按鈕
            btn_layout = QHBoxLayout()
            
            get_btn = QPushButton("📍")
            get_btn.setToolTip("獲取當前角度")
            get_btn.setMaximumWidth(40)
            get_btn.clicked.connect(lambda _, j=jid: self.get_current_joint_angle(j))
            btn_layout.addWidget(get_btn)
            
            set_btn = QPushButton("✓")
            set_btn.setToolTip("設置此關節")
            set_btn.setMaximumWidth(40)
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
        execute_btn.setMinimumHeight(40)
        execute_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        execute_btn.clicked.connect(self.execute_manual_move)
        execute_layout.addWidget(execute_btn)
        
        save_pos_btn = QPushButton("💾 保存為位置")
        save_pos_btn.setMinimumHeight(40)
        save_pos_btn.clicked.connect(self.save_manual_position)
        execute_layout.addWidget(save_pos_btn)
        
        layout.addLayout(execute_layout)
        layout.addStretch()
        
        return widget
    
    def create_position_manager_tab(self):
        """創建位置管理標籤頁"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # 預定義位置列表
        positions_group = QGroupBox("📍 已保存位置")
        positions_layout = QVBoxLayout()
        
        self.positions_table = QTableWidget()
        self.positions_table.setColumnCount(3)
        self.positions_table.setHorizontalHeaderLabels(['位置名稱', '關節角度', '操作'])
        self.positions_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        positions_layout.addWidget(self.positions_table)
        
        positions_group.setLayout(positions_layout)
        layout.addWidget(positions_group)
        
        # 位置操作
        pos_btn_layout = QHBoxLayout()
        
        refresh_pos_btn = QPushButton("🔄 刷新列表")
        refresh_pos_btn.clicked.connect(self.refresh_positions_list)
        pos_btn_layout.addWidget(refresh_pos_btn)
        
        goto_selected_btn = QPushButton("➡️ 移動到選定位置")
        goto_selected_btn.clicked.connect(self.goto_selected_position)
        pos_btn_layout.addWidget(goto_selected_btn)
        
        delete_pos_btn = QPushButton("🗑️ 刪除位置")
        delete_pos_btn.clicked.connect(self.delete_selected_position)
        pos_btn_layout.addWidget(delete_pos_btn)
        
        pos_btn_layout.addStretch()
        layout.addLayout(pos_btn_layout)
        
        # 導入/導出
        file_btn_layout = QHBoxLayout()
        
        load_positions_btn = QPushButton("📂 載入位置配置")
        load_positions_btn.clicked.connect(self.load_positions_from_file)
        file_btn_layout.addWidget(load_positions_btn)
        
        save_positions_btn = QPushButton("💾 保存位置配置")
        save_positions_btn.clicked.connect(self.save_positions_to_file)
        file_btn_layout.addWidget(save_positions_btn)
        
        file_btn_layout.addStretch()
        layout.addLayout(file_btn_layout)
        
        # 初始刷新
        self.refresh_positions_list()
        
        return widget
    
    def create_status_tab(self):
        """創建狀態監控標籤頁"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # 系統狀態
        status_group = QGroupBox("📊 系統狀態")
        status_layout = QGridLayout()
        
        self.status_labels = {
            'connection': QLabel("連接狀態: 檢查中..."),
            'hardware': QLabel("硬體狀態: 檢查中..."),
            'movement': QLabel("運動狀態: 停止"),
            'emergency': QLabel("緊急狀態: 正常"),
        }
        
        for i, (key, label) in enumerate(self.status_labels.items()):
            label.setFont(QFont("Microsoft JhengHei", 10))
            status_layout.addWidget(label, i // 2, i % 2)
        
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        # 當前位置
        position_group = QGroupBox("📍 當前位置")
        position_layout = QVBoxLayout()
        
        self.position_text = QTextEdit()
        self.position_text.setMaximumHeight(150)
        self.position_text.setReadOnly(True)
        position_layout.addWidget(self.position_text)
        
        refresh_btn = QPushButton("🔄 刷新狀態")
        refresh_btn.clicked.connect(self.update_status_display)
        position_layout.addWidget(refresh_btn)
        
        position_group.setLayout(position_layout)
        layout.addWidget(position_group)
        
        # 校正功能
        calib_group = QGroupBox("🔧 關節校正")
        calib_layout = QHBoxLayout()
        
        calib_layout.addWidget(QLabel("選擇關節:"))
        self.calib_combo = QComboBox()
        self.calib_combo.addItems([
            "Joint1 (基座)", "Joint2 (肩部)", "Joint3 (手肘)",
            "Joint4 (腕部俯仰)", "Joint5 (腕部旋轉)", "Joint6 (夾爪)"
        ])
        calib_layout.addWidget(self.calib_combo)
        
        calib_btn = QPushButton("🔧 校正")
        calib_btn.clicked.connect(self.calibrate_joint)
        calib_layout.addWidget(calib_btn)
        
        calib_all_btn = QPushButton("🔧 全部校正")
        calib_all_btn.clicked.connect(self.calibrate_all)
        calib_layout.addWidget(calib_all_btn)
        
        calib_group.setLayout(calib_layout)
        layout.addWidget(calib_group)
        
        layout.addStretch()
        return widget


    # 核心控制方法 
    
    def goto_predefined(self, position_name):
        """移動到預定義位置"""
        if not self.check_arm_available():
            return
        
        if self.emergency_stopped:
            self.add_log("⚠️ 緊急停止中，無法執行")
            return
        
        try:
            if position_name == 'home':
                # 確保夾爪關閉
                if self.arm_controller:
                    self.arm_controller.close_gripper()
                    time.sleep(0.5)
                    success = self.arm_controller.move_to_home()
                else:
                    success = True  # 模擬模式
                
                if success:
                    self.add_log(f"✅ 已移動到: {position_name} (夾爪已關閉)")
                else:
                    self.add_log(f"❌ 移動失敗: {position_name}")
            else:
                if self.arm_controller:
                    success = self.arm_controller.move_to_predefined(position_name)
                else:
                    success = True  # 模擬模式
                
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
                    msg = "打開夾爪 (73°)"
                else:
                    success = self.arm_controller.close_gripper()
                    msg = "關閉夾爪 (30°)"
            else:
                success = True  # 模擬模式
                msg = f"{'打開' if action == 'open' else '關閉'}夾爪 (模擬)"
            
            if success:
                self.add_log(f"✅ {msg}成功")
            else:
                self.add_log(f"❌ {msg}失敗")
        except Exception as e:
            self.add_log(f"❌ 錯誤: {e}")
    
    def execute_sorting_sequence(self, seq_type):
            """執行分類序列 - 三分類版本"""
            if not self.check_arm_available():
                return
            
            if self.emergency_stopped:
                self.add_log("⚠️ 緊急停止中，無法執行")
                return
            
            # 序列名稱映射
            seq_names = {
                'single': '單一缺陷',
                'double': '兩種缺陷',
                'multiple': '多種缺陷',
                'demo': '演示'
            }
            
            seq_name = seq_names.get(seq_type, seq_type)
            self.add_log(f"🤖 開始執行【{seq_name}】序列...")
            
            try:
                if self.arm_controller:
                    # 使用實際硬體
                    if seq_type == 'single':
                        self.execute_hardware_single_sequence()
                    elif seq_type == 'double':
                        self.execute_hardware_double_sequence()
                    elif seq_type == 'multiple':
                        self.execute_hardware_multiple_sequence()
                    elif seq_type == 'demo':
                        self.execute_hardware_demo_sequence()
                    else:
                        self.add_log(f"❌ 未知序列類型: {seq_type}")
                        return
                else:
                    # 模擬模式
                    self.execute_simulated_sequence(seq_type)
                
                # 發送完成信號
                self.action_completed.emit(seq_type, True)
                self.add_log(f"✅ 【{seq_name}】序列執行完成")
                
            except Exception as e:
                self.add_log(f"❌ 序列執行錯誤: {e}")
                self.action_completed.emit(seq_type, False)
    
    def execute_hardware_single_sequence(self):
        """執行單一缺陷硬體序列"""
        self.add_log("   📍 步驟1: 移動到安全高位")
        self.arm_controller.move_to_predefined('safe_high')
        time.sleep(0.5)
        
        self.add_log("   📍 步驟2: 移動到檢查位置")
        self.arm_controller.move_to_predefined('check')
        time.sleep(0.5)
        
        self.add_log("   📍 步驟3: 關閉夾爪抓取")
        self.arm_controller.close_gripper()
        time.sleep(1.0)
        
        self.add_log("   📍 步驟4: 抬升到安全高位")
        self.arm_controller.move_to_predefined('safe_high')
        time.sleep(0.5)
        
        self.add_log("   📍 步驟5: 移動到單一缺陷準備位置")
        self.arm_controller.move_to_predefined('single_defect_pickup')
        time.sleep(0.5)
        
        self.add_log("   📍 步驟6: 下降到單一缺陷放置區")
        self.arm_controller.move_to_predefined('single_defect_area')
        time.sleep(0.5)
        
        self.add_log("   📍 步驟7: 打開夾爪放置")
        self.arm_controller.open_gripper()
        time.sleep(1.0)
        
        self.add_log("   📍 步驟8: 返回安全高位")
        self.arm_controller.move_to_predefined('safe_high')
        time.sleep(0.5)
        
        self.add_log("   📍 步驟9: 返回原點")
        self.arm_controller.move_to_home()


    def execute_hardware_double_sequence(self):
        """執行兩種缺陷硬體序列"""
        self.add_log("   📍 步驟1: 移動到安全高位")
        self.arm_controller.move_to_predefined('safe_high')
        time.sleep(0.5)
        
        self.add_log("   📍 步驟2: 移動到檢查位置")
        self.arm_controller.move_to_predefined('check')
        time.sleep(0.5)
        
        self.add_log("   📍 步驟3: 關閉夾爪抓取")
        self.arm_controller.close_gripper()
        time.sleep(1.0)
        
        self.add_log("   📍 步驟4: 抬升到安全高位")
        self.arm_controller.move_to_predefined('safe_high')
        time.sleep(0.5)
        
        self.add_log("   📍 步驟5: 移動到兩種缺陷準備位置")
        self.arm_controller.move_to_predefined('double_defect_pickup')
        time.sleep(0.5)
        
        self.add_log("   📍 步驟6: 下降到兩種缺陷放置區")
        self.arm_controller.move_to_predefined('double_defect_area')
        time.sleep(0.5)
        
        self.add_log("   📍 步驟7: 打開夾爪放置")
        self.arm_controller.open_gripper()
        time.sleep(1.0)
        
        self.add_log("   📍 步驟8: 返回安全高位")
        self.arm_controller.move_to_predefined('safe_high')
        time.sleep(0.5)
        
        self.add_log("   📍 步驟9: 返回原點")
        self.arm_controller.move_to_home()


    def execute_hardware_multiple_sequence(self):
        """執行多種缺陷硬體序列"""
        self.add_log("   📍 步驟1: 移動到安全高位")
        self.arm_controller.move_to_predefined('safe_high')
        time.sleep(0.5)
        
        self.add_log("   📍 步驟2: 移動到檢查位置")
        self.arm_controller.move_to_predefined('check')
        time.sleep(0.5)
        
        self.add_log("   📍 步驟3: 關閉夾爪抓取")
        self.arm_controller.close_gripper()
        time.sleep(1.0)
        
        self.add_log("   📍 步驟4: 抬升到安全高位")
        self.arm_controller.move_to_predefined('safe_high')
        time.sleep(0.5)
        
        self.add_log("   📍 步驟5: 移動到多種缺陷準備位置")
        self.arm_controller.move_to_predefined('multiple_defect_pickup')
        time.sleep(0.5)
        
        self.add_log("   📍 步驟6: 下降到多種缺陷放置區")
        self.arm_controller.move_to_predefined('multiple_defect_area')
        time.sleep(0.5)
        
        self.add_log("   📍 步驟7: 打開夾爪放置")
        self.arm_controller.open_gripper()
        time.sleep(1.0)
        
        self.add_log("   📍 步驟8: 返回安全高位")
        self.arm_controller.move_to_predefined('safe_high')
        time.sleep(0.5)
        
        self.add_log("   📍 步驟9: 返回原點")
        self.arm_controller.move_to_home()


    def execute_hardware_demo_sequence(self):
        """執行演示序列 - 訪問所有三個分類區"""
        self.add_log("   📍 步驟1: 移動到原點")
        self.arm_controller.move_to_home()
        time.sleep(1.0)
        
        self.add_log("   📍 步驟2: 測試夾爪 - 打開")
        self.arm_controller.open_gripper()
        time.sleep(1.0)
        
        self.add_log("   📍 步驟3: 測試夾爪 - 關閉")
        self.arm_controller.close_gripper()
        time.sleep(1.0)
        
        self.add_log("   📍 步驟4: 移動到安全高位")
        self.arm_controller.move_to_predefined('safe_high')
        time.sleep(1.0)
        
        self.add_log("   📍 步驟5: 依序訪問三個分類區域")
        
        # 訪問單一缺陷區
        self.add_log("      🔵 訪問單一缺陷區")
        self.arm_controller.move_to_predefined('single_defect_area')
        time.sleep(1.5)
        
        # 返回安全高位
        self.arm_controller.move_to_predefined('safe_high')
        time.sleep(0.5)
        
        # 訪問兩種缺陷區
        self.add_log("      🟡 訪問兩種缺陷區")
        self.arm_controller.move_to_predefined('double_defect_area')
        time.sleep(1.5)
        
        # 返回安全高位
        self.arm_controller.move_to_predefined('safe_high')
        time.sleep(0.5)
        
        # 訪問多種缺陷區
        self.add_log("      🔴 訪問多種缺陷區")
        self.arm_controller.move_to_predefined('multiple_defect_area')
        time.sleep(1.5)
        
        self.add_log("   📍 步驟6: 返回安全高位")
        self.arm_controller.move_to_predefined('safe_high')
        time.sleep(1.0)
        
        self.add_log("   📍 步驟7: 返回原點")
        self.arm_controller.move_to_home()
    
    def execute_simulated_sequence(self, seq_type):
        """執行模擬序列 - 三分類版本"""
        seq_names = {
            'single': '單一缺陷',
            'double': '兩種缺陷',
            'multiple': '多種缺陷',
            'demo': '演示'
        }
        
        seq_name = seq_names.get(seq_type, seq_type)
        self.add_log(f"   [模擬模式] {seq_name}序列執行中...")
        time.sleep(2)
        self.add_log(f"   [模擬模式] {seq_name}序列執行完成")
        
    def execute_manual_move(self):
        """執行手動移動"""
        if not self.check_arm_available():
            return
        
        if self.emergency_stopped:
            self.add_log("⚠️ 緊急停止中,無法執行")
            return
        
        try:
            angles = [self.joint_sliders[f'joint{i+1}'].value() for i in range(6)]
            duration = self.duration_spin.value()
            
            self.add_log(f"🎯 手動移動: {angles}")
            
            if self.arm_controller:
                position = Position.from_list(angles)
                success = self.arm_controller.move_to_position(position, duration)  # ✅ 修復
            else:
                success = True  # 模擬模式
                self.add_log("   [模擬模式] 移動執行")
            
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
            self.add_log(f"📍 已獲取 {joint_id} 當前角度: {angle}°")
        else:
            self.add_log(f"📍 [模擬模式] {joint_id} 角度獲取")
    
    def set_single_joint(self, joint_id):
        """設置單個關節"""
        if not self.check_arm_available():
            return
        
        if self.emergency_stopped:
            self.add_log("⚠️ 緊急停止中，無法執行")
            return
        
        joint_index = int(joint_id[-1]) - 1
        angle = self.joint_sliders[joint_id].value()
        
        if self.arm_controller:
            success = self.arm_controller.move_joint(joint_index, angle, 15)
        else:
            success = True  # 模擬模式
        
        if success:
            self.add_log(f"✅ {joint_id} 已移動到 {angle}°")
        else:
            self.add_log(f"❌ {joint_id} 移動失敗")
    
    def save_manual_position(self):
        """保存手動位置"""
        name, ok = QInputDialog.getText(self, '保存位置', '請輸入位置名稱:')
        if ok and name.strip():
            angles = [self.joint_sliders[f'joint{i+1}'].value() for i in range(6)]
            
            if self.arm_controller:
                self.arm_controller.predefined_positions[name.strip()] = Position.from_list(angles)
            
            self.add_log(f"💾 位置已保存: {name.strip()} = {angles}")
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
        self.status_labels['emergency'].setStyleSheet("color: red; font-weight: bold;")
        
        QMessageBox.warning(self, "緊急停止", "系統已緊急停止！\n請檢查機械手臂狀態後點擊「恢復」按鈕。")
    
    def resume_operation(self):
        """恢復運行"""
        reply = QMessageBox.question(
            self, '確認恢復',
            '確認要恢復系統運行嗎？\n請確保機械手臂狀態安全。',
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
            self.status_labels['emergency'].setStyleSheet("color: green; font-weight: bold;")
    
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
            success = True  # 模擬模式
        
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
            '確定要校正所有關節嗎？這將需要幾分鐘時間。',
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.add_log("🔧 開始校正所有關節...")
            
            if self.arm_controller:
                success = self.arm_controller.calibrate_all_joints()
            else:
                success = True  # 模擬模式
            
            if success:
                self.add_log("✅ 所有關節校正完成")
            else:
                self.add_log("❌ 關節校正失敗")
    
    # 位置管理方法 
    
    def refresh_positions_list(self):
        """刷新位置列表"""
        self.positions_table.setRowCount(0)
        
        if self.arm_controller:
            positions = self.arm_controller.predefined_positions
        else:
            # 模擬模式的預設位置
            positions = {
                'home': Position(0, 180, 90, 90, 90, 73),
                'safe_high': Position(180, 120, 120, 90, 90, 73),
                'check': Position(90, 120, 100, 90, 90, 73),
                'rest': Position(90, 150, 120, 90, 90, 73),
            }
        
        for i, (name, position) in enumerate(positions.items()):
            self.positions_table.insertRow(i)
            
            # 位置名稱
            name_item = QTableWidgetItem(name)
            self.positions_table.setItem(i, 0, name_item)
            
            # 關節角度
            angles_str = ', '.join([f"{a:.0f}°" for a in position.to_list()])
            angles_item = QTableWidgetItem(angles_str)
            self.positions_table.setItem(i, 1, angles_item)
            
            # 操作按鈕
            btn_widget = QWidget()
            btn_layout = QHBoxLayout()
            btn_layout.setContentsMargins(2, 2, 2, 2)
            
            goto_btn = QPushButton("➡️")
            goto_btn.setToolTip("移動到此位置")
            goto_btn.clicked.connect(lambda _, n=name: self.goto_predefined(n))
            btn_layout.addWidget(goto_btn)
            
            load_btn = QPushButton("📥")
            load_btn.setToolTip("載入到滑桿")
            load_btn.clicked.connect(lambda _, p=position: self.load_position_to_sliders(p))
            btn_layout.addWidget(load_btn)
            
            btn_widget.setLayout(btn_layout)
            self.positions_table.setCellWidget(i, 2, btn_widget)
        
        self.add_log(f"🔄 已刷新位置列表 ({len(positions)} 個位置)")
    
    def load_position_to_sliders(self, position):
        """載入位置到滑桿"""
        angles = position.to_list()
        for i, angle in enumerate(angles):
            self.joint_sliders[f'joint{i+1}'].setValue(int(angle))
        self.add_log(f"📥 位置已載入到滑桿: {angles}")
    
    def goto_selected_position(self):
        """移動到選定位置"""
        current_row = self.positions_table.currentRow()
        if current_row < 0:
            self.add_log("⚠️ 請先選擇一個位置")
            return
        
        position_name = self.positions_table.item(current_row, 0).text()
        self.goto_predefined(position_name)
    
    def delete_selected_position(self):
        """刪除選定位置"""
        current_row = self.positions_table.currentRow()
        if current_row < 0:
            self.add_log("⚠️ 請先選擇一個位置")
            return
        
        position_name = self.positions_table.item(current_row, 0).text()
        
        # 不允許刪除系統預設位置
        system_positions = ['home', 'safe_high', 'check', 'rest', 'pass_area', 'fail_area', 
                        'pass_pickup', 'fail_pickup']
        if position_name in system_positions:
            QMessageBox.warning(self, "無法刪除", f"'{position_name}' 是系統預設位置,無法刪除。")
            return
        
        reply = QMessageBox.question(
            self, '確認刪除',
            f'確定要刪除位置 "{position_name}" 嗎?',
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if self.arm_controller:
                del self.arm_controller.predefined_positions[position_name]  # ✅ 修復
            
            self.add_log(f"🗑️ 已刪除位置: {position_name}")
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
                self.add_log(f"📂 已載入位置配置: {filename}")
                QMessageBox.information(self, '載入成功', f'已成功載入 {len(data)} 個位置！')
            except Exception as e:
                self.add_log(f"❌ 載入失敗: {e}")
                QMessageBox.critical(self, '錯誤', f'載入位置配置失敗：{e}')
    
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
                
                self.add_log(f"💾 已保存位置配置: {filename}")
                QMessageBox.information(self, '保存成功', f'位置配置已保存到：{filename}')
            except Exception as e:
                self.add_log(f"❌ 保存失敗: {e}")
                QMessageBox.critical(self, '錯誤', f'保存位置配置失敗：{e}')
    
    # 輔助方法 
    
    def check_arm_available(self):
        """檢查機械手臂是否可用"""
        if self.is_simulation_mode:
            return True  # 模擬模式總是返回True
        
        if not self.arm_controller or not self.arm_controller.is_connected:
            self.add_log("⚠️ 機械手臂未連接")
            QMessageBox.warning(self, "警告", "機械手臂未連接！\n請檢查連接後重新啟動程式。")
            return False
        return True
    
    def update_joint_label(self, joint_id, value):
        """更新關節標籤"""
        self.joint_labels[joint_id].setText(f"{value}°")
    
    def update_connection_status(self):
        """更新連接狀態"""
        if self.is_simulation_mode:
            status = "🟡 模擬模式"
            color = "#FF9800"
        elif self.arm_controller and self.arm_controller.is_connected:
            status = f"🟢 已連接到 {self.arm_controller.port}"
            color = "#4CAF50"
        else:
            status = "🔴 未連接"
            color = "#f44336"
        
        self.connection_label.setText(status)
        self.connection_label.setStyleSheet(
            f"background-color: {color}; color: white; padding: 5px; "
            f"font-weight: bold; border-radius: 3px;"
        )
    
    def update_status_display(self):
        """更新狀態顯示"""
        if self.is_simulation_mode:
            self.status_labels['connection'].setText("連接狀態: 🟡 模擬模式")
            self.status_labels['hardware'].setText("硬體狀態: 🟡 模擬運行")
            self.status_labels['movement'].setText("運動狀態: 🟢 就緒")
            
            # 模擬位置顯示
            text = "當前關節角度（模擬）：\n\n"
            for i in range(6):
                angle = self.joint_sliders[f'joint{i+1}'].value()
                joint_names = ["基座旋轉", "肩部俯仰", "手肘彎曲", "腕部俯仰", "腕部旋轉", "夾爪"]
                text += f"{joint_names[i]}: {angle}°\n"
            self.position_text.setPlainText(text)
            return
        
        if not self.arm_controller:
            self.status_labels['connection'].setText("連接狀態: 🔴 未連接")
            self.status_labels['hardware'].setText("硬體狀態: 🔴 不可用")
            self.status_labels['movement'].setText("運動狀態: 🔴 無法控制")
            return
        
        try:
            status = self.arm_controller.get_status()
            
            conn = "🟢 已連接" if status['hardware_available'] else "🔴 未連接"
            self.status_labels['connection'].setText(f"連接狀態: {conn}")
            
            hw = "🟢 正常" if status['hardware_available'] else "🔴 離線"
            self.status_labels['hardware'].setText(f"硬體狀態: {hw}")
            
            mv = "🟡 移動中" if status['is_moving'] else "🟢 停止"
            self.status_labels['movement'].setText(f"運動狀態: {mv}")
            
            # 更新位置顯示
            joint_info = self.arm_controller.get_joint_info()
            text = "當前關節角度：\n\n"
            for jid, info in joint_info.items():
                text += f"{info['name']}: {info['current_angle']:.1f}°\n"
            
            self.position_text.setPlainText(text)
            
        except Exception as e:
            self.add_log(f"⚠️ 狀態更新錯誤: {e}")
    
    def start_status_timer(self):
        """啟動狀態更新定時器"""
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status_display)
        self.status_timer.start(2000)  # 每2秒更新一次
    
    def add_log(self, message):
        """添加日誌"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        
        # 自動滾動到底部
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def closeEvent(self, event):
        """關閉事件"""
        if not self.is_simulation_mode and self.arm_controller and self.arm_controller.is_connected:
            reply = QMessageBox.question(
                self, '確認關閉',
                '關閉前是否要將機械手臂移動到原點位置？\n（夾爪將自動關閉）',
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
                    self.add_log(f"⚠️ 關閉時出錯: {e}")

        thr = getattr(self, 'arduino_thread', None)
        if thr and thr.isRunning():
            thr.stop()
            thr.wait(3000)

        
        event.accept()


# 測試程序
def main():
    """主函數 - 獨立運行測試"""
    from PyQt5.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    
    # 設置字體
    font = QFont("Microsoft JhengHei", 9)
    app.setFont(font)
    
    # 設置樣式
    app.setStyle('Fusion')
    
    # 創建控制窗口
    print("=" * 60)
    print("🤖 六軸機械手臂控制界面測試")
    print("=" * 60)
    
    # 嘗試連接機械手臂
    arm_controller = None
    if ARM_AVAILABLE:
        try:
            arm_controller = RoboticArmController()
            if not arm_controller.is_connected:
                print("⚠️ 機械手臂連接失敗，使用模擬模式")
                arm_controller = None
        except Exception as e:
            print(f"⚠️ 機械手臂初始化錯誤: {e}")
            arm_controller = None
    
    # 創建控制窗口
    window = ArmControlWidget(arm_controller=arm_controller)
    window.setWindowTitle("🤖 六軸機械手臂控制面板 v2.0")
    window.setGeometry(100, 100, 1000, 750)
    window.show()
    
    print("\n✅ 控制界面已啟動")
    if arm_controller:
        print(f"📡 已連接到: {arm_controller.port}")
    else:
        print("🟡 運行模式: 模擬模式")
    
    sys.exit(app.exec_())

class ArduinoSerialThread(QThread):
    evt_ir1 = pyqtSignal()
    evt_ir2 = pyqtSignal()
    log = pyqtSignal(str)

    def __init__(self, port=None, baud=115200, parent=None):
        super().__init__(parent)
        self.port = port
        self.baud = baud
        self._running = False
        self.ser = None

    def auto_find_port(self):
        for p in serial.tools.list_ports.comports():
            dev = p.device
            try:
                ident = _probe_ident(dev, baud=self.baud, timeout=0.25)
                if ident and ("IR CONTROL" in ident.upper() or "ARDUINO IR" in ident.upper()):
                    return dev
            except:
                pass
        return None

        
        # 如果沒找到 Arduino，列出所有可用 port
        if available_ports:
            self.log.emit(f"📋 可用 COM ports: {', '.join(available_ports)}")
        return None

    def try_connect_port(self, port):
        """嘗試連接指定的 COM port - 修復版本 (單次嘗試)"""
        try:
            ser = serial.Serial(port, self.baud, timeout=0.2)
            self.log.emit(f"[ArduinoSerial] ✅ 連接成功: {port}")
            return ser
        except serial.SerialException as e:
            if "PermissionError" in str(e) or "存取被拒" in str(e):
                self.log.emit(f"[ArduinoSerial] ❌ {port} 被其他程式佔用")
                self.log.emit(f"[ArduinoSerial] 💡 請關閉 Arduino IDE Serial Monitor 或其他佔用程序")
            elif "FileNotFoundError" in str(e) or "找不到" in str(e):
                self.log.emit(f"[ArduinoSerial] ❌ {port} 不存在")
            else:
                self.log.emit(f"[ArduinoSerial] ❌ 連接錯誤: {e}")
        except Exception as e:
            self.log.emit(f"[ArduinoSerial] ❌ 未預期錯誤: {e}")
        return None

    def send(self, line: str):
        """發送命令到 Arduino"""
        try:
            if self.ser and self.ser.is_open:
                if not line.endswith("\n"):
                    line += "\n"
                self.ser.write(line.encode("utf-8"))
                self.log.emit(f"[ArduinoSerial] → 發送: {line.strip()}")
            else:
                self.log.emit(f"[ArduinoSerial] ⚠️ 無法發送 '{line}' - Arduino 未連接")
        except Exception as e:
            self.log.emit(f"[ArduinoSerial] ❌ 發送失敗: {e}")

    def run(self):
        self._running = True
        connect_timeout = 5.0  # 5秒連線超時
        
        try:
            # 1) 決定 port
            if self.port:
                self.log.emit(f"[ArduinoSerial] 使用指定 port: {self.port}")
            else:
                self.log.emit("[ArduinoSerial] 開始自動掃描 Arduino...")
                self.port = self.auto_find_port()

            if not self.port:
                self.log.emit("[ArduinoSerial] 未找到可用的 Arduino port")
                return

            # 2) 嘗試連線 (加入超時)
            self.log.emit(f"[ArduinoSerial] 嘗試連接 {self.port}...")
            
            import time
            start_time = time.time()
            self.ser = None
            
            while time.time() - start_time < connect_timeout:
                self.ser = self.try_connect_port(self.port)
                if self.ser:
                    break
                time.sleep(0.5)
            
            if not self.ser:
                self.log.emit(f"[ArduinoSerial] 連線超時 ({connect_timeout}秒)")
                self.log.emit("[ArduinoSerial] 可能原因:")
                self.log.emit("   1. Arduino USB 線鬆脫")
                self.log.emit("   2. 其他程式佔用 COM port")
                self.log.emit("   3. Arduino 驅動未安裝")
                return

            self.log.emit(f"[ArduinoSerial] 連線成功: {self.port}")

            # 3) 讀取迴圈
            while self._running:
                try:
                    line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                    if not line:
                        continue

                    # 處理事件
                    if line == "EVT IR1":
                        self.evt_ir1.emit()
                        self.log.emit("[Arduino] IR1 觸發!")
                    elif line == "EVT IR2":
                        self.evt_ir2.emit()
                        self.log.emit("[Arduino] IR2 觸發!")
                    else:
                        # 處理其他回應
                        if line.startswith("OK"):
                            self.log.emit(f"[Arduino] {line}")
                        elif line.startswith("ERR"):
                            self.log.emit(f"[Arduino] 錯誤: {line}")
                        else:
                            self.log.emit(f"[Arduino] {line}")

                except Exception as e:
                    self.log.emit(f"[ArduinoSerial] read error: {e}")
                    break

        except Exception as e:
            self.log.emit(f"[ArduinoSerial] 執行錯誤: {e}")
        finally:
            try:
                if self.ser:
                    self.ser.close()
            except:
                pass
            self.log.emit("[ArduinoSerial] 已中斷連線")


class IRSensorThread(QThread):
    """IR感應器監控線程"""
    object_detected = pyqtSignal()
    sensor_state_changed = pyqtSignal(bool)
    
    def __init__(self, hardware, sensor_type='IR1'):
        super().__init__()
        self.hardware = hardware
        self.sensor_type = sensor_type
        self.running = False
        self.last_state = False
        self.debounce_time = 0.5
        self.last_trigger_time = 0
        
    def run(self):
        self._running = True
        try:
            # 1) 如果外部已指定 port，就只嘗試那一個
            if self.port:
                self.ser = self.try_connect_port(self.port)
                if not self.ser:
                    self.log.emit(f"[ArduinoSerial] ❌ 指定的 port 無法連線: {self.port}")
                    self.log.emit("[ArduinoSerial] 💡 請確認：COM 是否被佔用、板子是否正確、波特率是否一致")
                    return
            else:
                # 2) 沒指定 port 才允許自動找
                self.port = self.auto_find_port()
                if not self.port:
                    self.log.emit("[ArduinoSerial] ❌ 未找到可用的 Arduino port")
                    return
                self.ser = self.try_connect_port(self.port)
                if not self.ser:
                    self.log.emit(f"[ArduinoSerial] ❌ 無法連接 {self.port}")
                    return

            # 3) 進入讀取迴圈
            while self._running:
                try:
                    line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                    if not line:
                        continue
                    if line == "EVT IR1":
                        self.evt_ir1.emit()
                        self.log.emit("[Arduino] 🎯 IR1 觸發!")
                    elif line == "EVT IR2":
                        self.evt_ir2.emit()
                        self.log.emit("[Arduino] 🎯 IR2 觸發!")
                    else:
                        self.log.emit(f"[Arduino] ℹ️  {line}")
                except Exception as e:
                    self.log.emit(f"[ArduinoSerial] read error: {e}")
                    break
        finally:
            try:
                if self.ser:
                    self.ser.close()
            except:
                pass
            self.log.emit("[ArduinoSerial] disconnected.")

    
    def stop(self):
        """停止監控"""
        self.running = False
        print(f"🛑 {self.sensor_type}感應器監控已停止")


class PCBADetectionSystem(QMainWindow):
    """PCB檢測系統主界面 - 整合三分類"""
    
    def __init__(self):
        super().__init__()
        
        print("=" * 70)
        print("🚀 PCB檢測系統啟動中...")
        print("=" * 70)
        
        # 步驟 1: COM Port 分配 
        print("\n[步驟1/6] 🔍 開始 COM Port 自動分配...")
        try:
            ir_port, arm_port, dbg = auto_assign_com_ports_safely()
            for line in dbg:
                print(f"  {line}")
            print(f"✅ COM Port 分配完成: IR={ir_port}, ARM={arm_port}")
        except Exception as e:
            print(f"⚠️ COM Port 分配失敗: {e}")
            ir_port, arm_port = None, None
        
        self.ir_port = ir_port
        self.arm_port = arm_port
        
        # 步驟 2: 初始化基本屬性 
        print("\n[步驟2/6] 📋 初始化系統屬性...")
        self.arduino_thread = None
        self.camera_thread = None
        self.arm_controller = None
        self.robotic_arm_controller = None
        self.arm_control_window = None
        
        self.is_running = False
        self.conveyor_running = False
        self.ir1_detection_enabled = False
        self.ir2_detection_enabled = False
        
        self.last_detection_result = None
        self.last_defect_list = []
        self.last_detection_image = None
        self.classification_mode = "three_class"
        print("✅ 系統屬性初始化完成")
        
        #  步驟 3: 硬體初始化 (相機) 
        print("\n[步驟3/6] 📷 初始化硬體控制器...")
        try:
            self.hardware = HardwareController()
            print("  - 正在初始化相機...")
            self.hardware.init_hardware()  # 這裡可能卡住!
            print("✅ 硬體控制器初始化完成")
        except Exception as e:
            print(f"⚠️ 硬體初始化失敗: {e}")
            # 建立一個假的 hardware 物件避免後續錯誤
            self.hardware = type('HardwareController', (), {
                'get_camera_frame': lambda: None,
                'init_hardware': lambda: None,
                'cleanup': lambda: None,
                'get_hardware_status': lambda: {'camera_available': False}
            })()
        
        #  步驟 4: DataManager & ImageProcessor 
        print("\n[步驟4/6] 🧠 初始化資料管理與影像處理...")
        self.data_manager = DataManager()
        self.current_model_path = "best.pt"
        self.image_processor = None
        
        try:
            self.init_image_processor()
            print("✅ 影像處理器初始化完成")
        except Exception as e:
            print(f"⚠️ 影像處理器初始化失敗: {e}")
        
        #  步驟 5: UI 初始化 
        print("\n[步驟5/6] 🎨 建立使用者界面...")
        try:
            self.init_ui()
            self.setup_styles()
            print("✅ UI 初始化完成")
        except Exception as e:
            print(f"❌ UI 初始化失敗: {e}")
            raise
        
        #  步驟 6: 執行緒啟動 
        print("\n[步驟6/6] 🔄 啟動背景執行緒...")
        try:
            self.setup_threads()  # 這裡也可能卡住!
            print("✅ 執行緒啟動完成")
        except Exception as e:
            print(f"⚠️ 執行緒啟動失敗: {e}")
        
        #  完成初始化 
        print("\n" + "=" * 70)
        print("✅ PCB檢測系統初始化完成!")
        print("=" * 70 + "\n")
        
        self.update_status_displays()
        
        if not ir_port:
            self.log_message("❌ 未分配到 IR COM,請確認 UNO 已連線")
        
        #  最後加入連線診斷 
        print("\n" + "🔍"*30)
        print("系統連線診斷")
        print("🔍"*30)
        
        # 檢查 Arduino 線程
        if hasattr(self, 'arduino_thread') and self.arduino_thread:
            print(f"✅ Arduino 線程已建立")
            print(f"   運行中: {self.arduino_thread.isRunning()}")
            
            if hasattr(self.arduino_thread, 'ser'):
                ser = self.arduino_thread.ser
                if ser:
                    print(f"   Serial 物件: 存在")
                    print(f"   Port: {ser.port if hasattr(ser, 'port') else 'N/A'}")
                    print(f"   已開啟: {ser.is_open if hasattr(ser, 'is_open') else 'N/A'}")
                else:
                    print(f"   ❌ Serial 物件為 None")
            else:
                print(f"   ❌ Arduino 線程沒有 ser 屬性")
        else:
            print(f"❌ Arduino 線程未建立")
        
        # 測試發送指令
        print("\n📤 測試發送 PING 指令...")
        if self._arduino_connected():
            try:
                self.arduino_thread.send("PING")
                print("   ✅ PING 已發送 (等待 Arduino 回應 PONG)")
            except Exception as e:
                print(f"   ❌ 發送失敗: {e}")
        else:
            print("   ❌ Arduino 未連線,無法發送")
        
        print("🔍"*30 + "\n")


    def log_message(self, msg: str):
        """統一 UI/console 日誌輸出，避免 AttributeError"""
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"

        # 1) 一律印到 console（目前 thread log 也都接 print）
        print(line)

        # 2) 如果你之後有放 QTextEdit 叫做 system_log_text，就順便寫進去
        w = getattr(self, "system_log_text", None)
        if w is not None:
            try:
                w.append(line)
            except Exception:
                pass

        # 3) 狀態列（有就顯示，沒有就略過）
        try:
            self.statusBar().showMessage(msg, 5000)
        except Exception:
            pass

    
    def init_image_processor(self):
        """初始化影像處理器"""
        try:
            # 搜尋模型檔案
            model_paths = [
                "best.pt",
                "last.pt",
                "runs/detect/train/weights/best.pt",
                "yolov8n.pt"
            ]
            
            model_found = None
            for path in model_paths:
                if os.path.exists(path):
                    model_found = path
                    print(f"✅ 找到模型: {path}")
                    break
            
            if model_found:
                self.current_model_path = model_found
            else:
                print("⚠️ 未找到訓練模型")
            
            # 定義檢測類別
            custom_classes = {
                0: 'mb',
                1: 'op',
                2: 'sc',
            }
            
            # 創建影像處理器
            self.image_processor = ImageProcessor(
                model_path=self.current_model_path,
                class_names=custom_classes
            )
            
            print("✅ 影像處理器初始化成功")
            
        except Exception as e:
            print(f"❌ 影像處理器初始化失敗: {e}")
            self.image_processor = None
    
    def init_ui(self):
        """初始化用戶界面"""
        title = "PCB 缺陷檢測系統 v4.0 - 鼠咬/斷路/雜銅檢測 (三分類系統)"
        if JETSON_ENV:
            title += " (Jetson Orin Nano)"
        
        self.setWindowTitle(title)
        self.setGeometry(100, 100, 1400, 900)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)
        
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)
        
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)
        
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([840, 560])
    
    def create_left_panel(self):
        """創建左側面板"""
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_widget.setLayout(left_layout)
        
        # 雙視窗影像區域
        camera_group = QGroupBox("📷 即時影像監控")
        camera_layout = QVBoxLayout()
        
        dual_display_layout = QHBoxLayout()
        
        # 即時影像
        realtime_group = QGroupBox("🎥 即時影像")
        realtime_layout = QVBoxLayout()
        
        self.original_image_display = QLabel("即時影像預覽區")
        self.original_image_display.setMinimumHeight(400)
        self.original_image_display.setMinimumWidth(360)
        self.original_image_display.setAlignment(Qt.AlignCenter)
        self.original_image_display.setStyleSheet("""
            QLabel {
                border: 2px solid #4CAF50;
                border-radius: 6px;
                background-color: #f8f9fa;
                font-size: 14px;
                font-weight: bold;
                color: #666;
            }
        """)
        realtime_layout.addWidget(self.original_image_display)
        realtime_group.setLayout(realtime_layout)
        
        # 檢測結果
        detection_group = QGroupBox("🤖 YOLOv12檢測結果")
        detection_layout = QVBoxLayout()
        
        self.detection_image_display = QLabel("YOLOv12檢測結果\n等待檢測...")
        self.detection_image_display.setMinimumHeight(400)
        self.detection_image_display.setMinimumWidth(360)
        self.detection_image_display.setAlignment(Qt.AlignCenter)
        self.detection_image_display.setStyleSheet("""
            QLabel {
                border: 2px solid #2196F3;
                border-radius: 6px;
                background-color: #f0f8ff;
                font-size: 14px;
                font-weight: bold;
                color: #666;
            }
        """)
        detection_layout.addWidget(self.detection_image_display)
        detection_group.setLayout(detection_layout)
        
        dual_display_layout.addWidget(realtime_group)
        dual_display_layout.addWidget(detection_group)
        
        camera_layout.addLayout(dual_display_layout)
        camera_group.setLayout(camera_layout)
        left_layout.addWidget(camera_group)
        
        # 控制面板
        control_panel = self.create_control_panel()
        left_layout.addWidget(control_panel)
        # 隱藏舊版單軸伺服角度控制
        if hasattr(self, "servo_slider"):
            self.servo_slider.hide()
        if hasattr(self, "servo_label"):
            self.servo_label.hide()

        
        # 檢測記錄表格
        log_group = self.create_log_panel()
        left_layout.addWidget(log_group)
        
        return left_widget
    
    def create_control_panel(self):
        """創建控制面板"""
        control_group = QGroupBox("🎮 系統控制")
        control_layout = QVBoxLayout()

        # 第一行：啟動 / 輸送帶 / 重設
        row1 = QHBoxLayout()

        self.start_btn = QPushButton("▶️ 啟動檢測")
        self.start_btn.clicked.connect(self.toggle_detection)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)

        self.conveyor_btn = QPushButton("🎬 啟動輸送帶")
        self.conveyor_btn.clicked.connect(self.toggle_conveyor)
        self.conveyor_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
        """)

        self.reset_btn = QPushButton("🔄 系統重設")
        self.reset_btn.clicked.connect(self.reset_system)
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)

        row1.addWidget(self.start_btn)
        row1.addWidget(self.conveyor_btn)
        row1.addWidget(self.reset_btn)
        control_layout.addLayout(row1)

        # 第二行：IR 控制 + 機械手臂
        row2 = QHBoxLayout()

        self.ir1_btn = QPushButton("🔴 啟用IR1自動檢測")
        self.ir1_btn.clicked.connect(self.toggle_ir1_detection)
        self.ir1_btn.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                font-size: 13px;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
        """)

        self.ir2_btn = QPushButton("🟠 啟用IR2自動分類")
        self.ir2_btn.clicked.connect(self.toggle_ir2_detection)
        self.ir2_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF5722;
                color: white;
                font-size: 13px;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #E64A19;
            }
        """)

        self.arm_control_btn = QPushButton("🤖 機械手臂控制")
        self.arm_control_btn.clicked.connect(self.show_arm_control)
        self.arm_control_btn.setStyleSheet("""
            QPushButton {
                background-color: #00BCD4;
                color: white;
                font-size: 13px;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #0097A7;
            }
        """)

        row2.addWidget(self.ir1_btn)
        row2.addWidget(self.ir2_btn)
        row2.addWidget(self.arm_control_btn)
        control_layout.addLayout(row2)

        #  滑桿閾值 
        sliders_layout = QGridLayout()

        

        # 檢測閾值
        self.threshold_label = QLabel("檢測閾值: 0.50")
        sliders_layout.addWidget(self.threshold_label, 1, 0)

        self.threshold_slider = QSlider(Qt.Horizontal)
        self.threshold_slider.setMinimum(0)
        self.threshold_slider.setMaximum(100)
        self.threshold_slider.setValue(50)
        self.threshold_slider.valueChanged.connect(self.update_threshold)
        sliders_layout.addWidget(self.threshold_slider, 1, 1)

        control_layout.addLayout(sliders_layout)


        # 第三行：📷 手動辨識 + 📂 載入模型
        row3 = QHBoxLayout()

        # 手動辨識
        # 📷 手動辨識按鈕（單張）
        self.manual_detect_btn = QPushButton("📷 手動辨識(單張)")
        self.manual_detect_btn.setMinimumHeight(40)
        self.manual_detect_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold;"
        )
        
        self.manual_detect_btn.clicked.connect(self.execute_detection)

        # 加到控制區域 Layout
        control_layout.addWidget(self.manual_detect_btn)


        # 保留原本的「載入模型」功能鍵
        self.load_model_btn = QPushButton("📂 載入模型")
        self.load_model_btn.clicked.connect(self.choose_model_file)
        self.load_model_btn.setStyleSheet("""
            QPushButton {
                background-color: #607D8B;
                color: white;
                font-size: 13px;
                font-weight: bold;
                padding: 8px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #455A64;
            }
        """)
        row3.addWidget(self.load_model_btn)

        control_layout.addLayout(row3)

        control_group.setLayout(control_layout)
        return control_group

    
    def create_log_panel(self):
        """創建檢測記錄面板"""
        log_group = QGroupBox("📋 檢測記錄")
        log_layout = QVBoxLayout()
        
        self.log_table = QTableWidget()
        self.log_table.setColumnCount(6)
        self.log_table.setHorizontalHeaderLabels([
            "時間", "結果", "缺陷類型", "分類", "信心度", "備註"
        ])
        self.log_table.setAlternatingRowColors(True)
        self.log_table.horizontalHeader().setStretchLastSection(True)
        
        log_layout.addWidget(self.log_table)
        log_group.setLayout(log_layout)
        
        return log_group
    
    def create_right_panel(self):
        """創建右側面板"""
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_widget.setLayout(right_layout)
        
        # 狀態顯示
        status_group = self.create_status_panel()
        right_layout.addWidget(status_group)
        
        # 統計資訊
        stats_group = self.create_statistics_panel()
        right_layout.addWidget(stats_group)
        
        # 功能按鈕
        function_group = self.create_function_panel()
        right_layout.addWidget(function_group)
        
        right_layout.addStretch()
        
        return right_widget
    
    def create_status_panel(self):
        """創建狀態面板"""
        status_group = QGroupBox("📊 系統狀態")
        status_layout = QVBoxLayout()
        
        self.camera_status = QLabel("相機狀態: 🔴 離線")
        self.servo_status = QLabel("分類系統: ⚙️ 待命")
        self.ir1_status = QLabel("IR1狀態: 🔴 關閉")
        self.ir2_status = QLabel("IR2狀態: 🔴 關閉")
        self.model_status_label = QLabel("模型狀態: ⚠️ 未載入")
        self.model_info_label = QLabel("模型資訊: -")
        self.classification_mode_label = QLabel("分類模式: 🎨 三分類")
        
        for label in [self.camera_status, self.servo_status, self.ir1_status,
                     self.ir2_status, self.model_status_label, self.model_info_label,
                     self.classification_mode_label]:
            label.setStyleSheet("font-size: 12px; padding: 5px;")
            status_layout.addWidget(label)
        
        status_group.setLayout(status_layout)
        return status_group
    
    def create_statistics_panel(self):
        """創建統計面板"""
        stats_group = QGroupBox("📈 檢測統計")
        stats_layout = QVBoxLayout()
        
        self.total_label = QLabel("總檢測數: 0")
        self.pass_label = QLabel("合格數: 0")
        self.defect_label = QLabel("缺陷數: 0")
        self.pass_rate_label = QLabel("合格率: 0.0%")
        
        self.single_defect_label = QLabel("🔵 單一缺陷: 0")
        self.double_defect_label = QLabel("🟡 兩種缺陷: 0")
        self.multiple_defect_label = QLabel("🔴 多種缺陷: 0")
        
        for label in [self.total_label, self.pass_label, self.defect_label,
                     self.pass_rate_label, self.single_defect_label,
                     self.double_defect_label, self.multiple_defect_label]:
            label.setStyleSheet("font-size: 12px; padding: 5px;")
            stats_layout.addWidget(label)
        
        stats_group.setLayout(stats_layout)
        return stats_group
    
    def create_function_panel(self):
        """創建功能面板"""
        function_group = QGroupBox("🔧 功能選項")
        function_layout = QVBoxLayout()
        
        # 相機選擇
        camera_layout = QHBoxLayout()
        camera_label = QLabel("相機索引:")
        self.camera_index_spin = QSpinBox()
        self.camera_index_spin.setMinimum(0)
        self.camera_index_spin.setMaximum(10)
        self.camera_index_spin.setValue(0)
        
        camera_switch_btn = QPushButton("切換相機")
        camera_switch_btn.clicked.connect(self.switch_camera)
        
        camera_layout.addWidget(camera_label)
        camera_layout.addWidget(self.camera_index_spin)
        camera_layout.addWidget(camera_switch_btn)
        function_layout.addLayout(camera_layout)
        
        # 匯出按鈕
        export_txt_btn = QPushButton("📄 匯出TXT報告")
        export_txt_btn.clicked.connect(self.export_txt_report)
        function_layout.addWidget(export_txt_btn)
        
        export_csv_btn = QPushButton("📊 匯出CSV數據")
        export_csv_btn.clicked.connect(self.export_csv_data)
        function_layout.addWidget(export_csv_btn)
        
        clear_btn = QPushButton("🗑️ 清除記錄")
        clear_btn.clicked.connect(self.clear_records)
        function_layout.addWidget(clear_btn)
        
        function_group.setLayout(function_layout)
        return function_group
    
    def setup_styles(self):
        """設置樣式"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #ddd;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
    
    def setup_threads(self):
        """設置線程 - 加入超時保護"""
        
        # 1️⃣ 相機線程
        print("  - 啟動相機線程...")
        try:
            if not getattr(self, "camera_thread", None):
                self.camera_thread = CameraThread(self.hardware)
                self.camera_thread.frame_ready.connect(self.update_camera_display)
            print("    ✅ 相機線程建立完成")
        except Exception as e:
            print(f"    ⚠️ 相機線程建立失敗: {e}")

        # 2️⃣ Arduino Serial Thread (加入超時保護)
        print("  - 啟動 Arduino 通訊線程...")
        try:
            if not getattr(self, "arduino_thread", None):
                self.arduino_thread = ArduinoSerialThread(
                    port=self.ir_port, 
                    baud=115200
                )
                self.arduino_thread.evt_ir1.connect(self.on_ir1_triggered)
                self.arduino_thread.evt_ir2.connect(self.on_ir2_triggered)
                self.arduino_thread.log.connect(print)
                
                if not self.arduino_thread.isRunning():
                    self.arduino_thread.start()
                    print("    ✅ Arduino 線程已啟動 (非阻塞)")
            else:
                print("    ℹ️ Arduino 線程已存在,跳過")
        except Exception as e:
            print(f"    ⚠️ Arduino 線程啟動失敗: {e}")


        
    def toggle_detection(self):
        """切換檢測狀態"""
        if not self.is_running:
            self.start_detection()
        else:
            self.stop_detection()
    
    def start_detection(self):
        """開始檢測"""
        self.is_running = True
        self.start_btn.setText("⏹️ 停止檢測")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
        """)
        
        if self.camera_thread and not self.camera_thread.isRunning():
            self.camera_thread.start()
        
        print("▶️ 檢測已啟動")
    
    def stop_detection(self):
        """停止檢測"""
        self.is_running = False
        self.start_btn.setText("▶️ 啟動檢測")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
        """)
        
        if self.camera_thread and self.camera_thread.isRunning():
            self.camera_thread.stop()
        
        print("⏹️ 檢測已停止")
    
    def toggle_conveyor(self):
        """切換輸送帶狀態 - 完整診斷與修復版"""
        print("\n" + "="*70)
        print("🎬 輸送帶控制")
        print("="*70)
        
        # 診斷 1: 檢查 Arduino 線程
        t = getattr(self, "arduino_thread", None)
        
        if t is None:
            print("❌ Arduino 線程不存在")
            print("💡 系統可能尚未正確初始化")
            print("="*70 + "\n")
            QMessageBox.critical(
                self, "錯誤", 
                "Arduino 線程未初始化\n請重新啟動程式"
            )
            return
        
        print(f"✅ Arduino 線程存在")
        
        # 診斷 2: 檢查線程運行狀態
        if not t.isRunning():
            print("❌ Arduino 線程未運行")
            print("💡 嘗試重新啟動線程...")
            
            try:
                t.start()
                time.sleep(1)
                
                if t.isRunning():
                    print("✅ 線程已重新啟動")
                else:
                    print("❌ 線程重啟失敗")
                    print("="*70 + "\n")
                    QMessageBox.critical(
                        self, "錯誤",
                        "Arduino 線程無法啟動\n請檢查 COM port 連線"
                    )
                    return
            except Exception as e:
                print(f"❌ 重啟失敗: {e}")
                print("="*70 + "\n")
                return
        
        print(f"✅ Arduino 線程運行中")
        
        # 診斷 3: 檢查 Serial 物件
        if not hasattr(t, 'ser') or t.ser is None:
            print("❌ Arduino 線程沒有 Serial 物件")
            print("="*70 + "\n")
            QMessageBox.critical(
                self, "錯誤",
                "Arduino Serial 未初始化\n請重新啟動程式"
            )
            return
        
        print(f"✅ Serial 物件存在")
        
        # 診斷 4: 檢查 Serial 開啟狀態
        if not hasattr(t.ser, 'is_open') or not t.ser.is_open:
            print("❌ Serial Port 未開啟")
            print(f"   Port: {t.ser.port if hasattr(t.ser, 'port') else 'N/A'}")
            print("="*70 + "\n")
            QMessageBox.critical(
                self, "錯誤",
                f"COM Port 未開啟\n請檢查 {t.port} 是否被佔用"
            )
            return
        
        print(f"✅ Serial Port 已開啟: {t.ser.port}")
        
        # 診斷 5: 檢查當前狀態 
        if not hasattr(self, "conveyor_running"):
            self.conveyor_running = True
            print("⚠️ conveyor_running 未初始化,預設為 True")
        
        current_state = "運行中" if self.conveyor_running else "已停止"
        print(f"📊 當前輸送帶狀態: {current_state}")
        
        #  執行控制 
        try:
            if self.conveyor_running:
                # 停止輸送帶
                print("\n📤 發送指令: CONV_OFF")
                t.send("CONV_OFF")
                
                # 等待 Arduino 處理
                time.sleep(0.3)
                
                self.conveyor_running = False
                self.conveyor_btn.setText("🎬 啟動輸送帶")
                self.conveyor_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #2196F3;
                        color: white;
                        font-size: 14px;
                        font-weight: bold;
                        padding: 10px;
                        border-radius: 5px;
                    }
                """)
                print("✅ 輸送帶停止指令已發送")
                print("   等待 Arduino 回應 'OK CONV_OFF'")
                
            else:
                # 啟動輸送帶
                print("\n📤 發送指令: CONV_ON")
                t.send("CONV_ON")
                
                # 等待 Arduino 處理
                time.sleep(0.3)
                
                self.conveyor_running = True
                self.conveyor_btn.setText("🛑 停止輸送帶")
                self.conveyor_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #f44336;
                        color: white;
                        font-size: 14px;
                        font-weight: bold;
                        padding: 10px;
                        border-radius: 5px;
                    }
                """)
                print("✅ 輸送帶啟動指令已發送")
                print("   等待 Arduino 回應 'OK CONV_ON'")
        
        except Exception as e:
            print(f"\n❌ 發送指令時發生錯誤:")
            print(f"   {e}")
            import traceback
            traceback.print_exc()
            
            QMessageBox.critical(
                self, "錯誤",
                f"輸送帶控制失敗:\n{e}"
            )
        
        print("="*70 + "\n")

    def send_command(self, cmd: str):
        if not cmd.endswith("\n"):
            cmd += "\n"
        self.serial.write(cmd.encode("utf-8"))

    
    def _arduino_connected(self) -> bool:
        return bool(self.arduino_thread and self.arduino_thread.ser and self.arduino_thread.ser.is_open)


    def toggle_ir1_detection(self):
        if not self.ir1_detection_enabled:
            if not self._arduino_connected():
                print("⚠️ Arduino 未連線，無法啟用 IR1（請先確認 COM 連線成功）")
                self.ir1_detection_enabled = False
                return

            self.ir1_detection_enabled = True
            self.ir1_btn.setText("🟢 IR1自動檢測中")
            self.ir1_status.setText("IR1狀態: 🟢 運行中")
            self.arduino_thread.send("IR1_ON")
            print("🔍 IR1自動檢測已啟用 (USB)")

        else:
            self.ir1_detection_enabled = False
            self.ir1_btn.setText("🔴 啟用IR1自動檢測")
            self.ir1_status.setText("IR1狀態: 🔴 關閉")
            self.arduino_thread.send("IR1_OFF")
            print("🛑 IR1自動檢測已停用 (USB)")


    def toggle_ir2_detection(self):
        if not self.ir2_detection_enabled:
            if not self._arduino_connected():
                print("⚠️ Arduino 未連線，無法啟用 IR2（請先確認 COM 連線成功）")
                self.ir2_detection_enabled = False
                return

            self.ir2_detection_enabled = True
            self.ir2_btn.setText("🟢 IR2自動檢測中")
            self.ir2_status.setText("IR2狀態: 🟢 運行中")
            self.arduino_thread.send("IR2_ON")
            print("🔍 IR2自動分類已啟用 (USB)")

        else:
            self.ir2_detection_enabled = False
            self.ir2_btn.setText("🟠 啟用IR2自動分類")
            self.ir2_status.setText("IR2狀態: 🟠 關閉")
            self.arduino_thread.send("IR2_OFF")
            print("🛑 IR2自動分類已停用 (USB)")



    
    def show_arm_control(self):
        """顯示機械手臂控制視窗 - 診斷版"""
        print("\n" + "="*60)
        print("🤖 機械手臂控制視窗診斷")
        print("="*60)
        
        # 檢查屬性
        print(f"arm_control_window 存在: {hasattr(self, 'arm_control_window')}")
        print(f"robotic_arm_controller 存在: {hasattr(self, 'robotic_arm_controller')}")
        print(f"arm_port: {getattr(self, 'arm_port', 'N/A')}")
        print(f"ARM_CONTROLLER_AVAILABLE: {ARM_CONTROLLER_AVAILABLE}")
        
        # 確保屬性存在
        if not hasattr(self, "arm_control_window"):
            self.arm_control_window = None
        if not hasattr(self, "robotic_arm_controller"):
            self.robotic_arm_controller = None

        # 若尚未初始化機械手臂控制器
        if self.robotic_arm_controller is None:
            if not getattr(self, "arm_port", None):
                print("❌ 未分配到機械手臂 COM")
                print("="*60 + "\n")
                QMessageBox.warning(self, "警告", "未分配到機械手臂 COM\n請檢查連線")
                return
            
            if not ARM_CONTROLLER_AVAILABLE:
                print("❌ 機械手臂控制模組不可用")
                print("="*60 + "\n")
                QMessageBox.warning(self, "警告", "機械手臂控制模組未載入")
                return

            try:
                print(f"🔌 嘗試連線到 {self.arm_port}...")
                
               
                self.robotic_arm_controller = RoboticArmController(
                    port=self.arm_port,
                    baudrate=115200
                )
                
                if self.robotic_arm_controller.is_connected:
                    print(f"✅ 機械手臂已連線: {self.arm_port}")
                else:
                    print(f"⚠️ 機械手臂連線失敗,但物件已建立")
                    
            except Exception as e:
                print(f"❌ 機械手臂連線失敗: {e}")
                import traceback
                traceback.print_exc()
                self.robotic_arm_controller = None
                print("="*60 + "\n")
                QMessageBox.critical(
                    self, "錯誤", 
                    f"機械手臂連線失敗:\n{e}\n\n請檢查:\n"
                    f"1. COM port 是否正確 ({self.arm_port})\n"
                    f"2. Arduino 程式是否已上傳\n"
                    f"3. 是否有其他程式佔用 port"
                )
                return
        
        print("="*60 + "\n")
        
        # 建立/顯示視窗
        if self.arm_control_window is None or not self.arm_control_window.isVisible():
            self.arm_control_window = OldArmControlWidget(self.robotic_arm_controller)
            self.arm_control_window.action_completed.connect(self.on_arm_action_completed)
            self.arm_control_window.show()
        else:
            self.arm_control_window.raise_()
            self.arm_control_window.activateWindow()

    def on_arm_action_completed(self, target, success):
        """機械手臂動作完成回調"""
        if success:
            print(f"✅ 機械手臂分類完成: {target}")
        else:
            print(f"❌ 機械手臂分類失敗: {target}")
    
    def _conv_off(self):
        """停止輸送帶 - 強化版"""
        print("\n[_conv_off] 嘗試停止輸送帶")
        
        # 1 透過 Arduino Serial
        t = getattr(self, "arduino_thread", None)
        if t and t.isRunning():
            if hasattr(t, 'ser') and t.ser and hasattr(t.ser, 'is_open') and t.ser.is_open:
                try:
                    print("   → 透過 Arduino 發送 CONV_OFF")
                    t.send("CONV_OFF")
                    time.sleep(0.2)  # 給 Arduino 處理時間
                    
                    self.conveyor_running = False
                    print("   ✅ 指令已發送")
                    return True
                except Exception as e:
                    print(f"   ❌ Arduino 發送失敗: {e}")
        
        # 2 透過 Hardware Controller (fallback)
        if hasattr(self, "hardware") and self.hardware:
            if hasattr(self.hardware, "stop_conveyor"):
                try:
                    print("   → 透過 Hardware 停止")
                    self.hardware.stop_conveyor()
                    self.conveyor_running = False
                    print("   ✅ Hardware 停止成功")
                    return True
                except Exception as e:
                    print(f"   ❌ Hardware 停止失敗: {e}")
        
        print("   ❌ 所有方法都失敗\n")
        return False

    def _conv_on(self):
        """啟動輸送帶 - 強化版"""
        print("\n[_conv_on] 嘗試啟動輸送帶")
        
        # 1 透過 Arduino Serial
        t = getattr(self, "arduino_thread", None)
        if t and t.isRunning():
            if hasattr(t, 'ser') and t.ser and hasattr(t.ser, 'is_open') and t.ser.is_open:
                try:
                    print("   → 透過 Arduino 發送 CONV_ON")
                    t.send("CONV_ON")
                    time.sleep(0.2)
                    
                    self.conveyor_running = True
                    print("   ✅ 指令已發送")
                    return True
                except Exception as e:
                    print(f"   ❌ Arduino 發送失敗: {e}")
        
        # 2 透過 Hardware Controller (fallback)
        if hasattr(self, "hardware") and self.hardware:
            if hasattr(self.hardware, "start_conveyor"):
                try:
                    print("   → 透過 Hardware 啟動")
                    self.hardware.start_conveyor()
                    self.conveyor_running = True
                    print("   ✅ Hardware 啟動成功")
                    return True
                except Exception as e:
                    print(f"   ❌ Hardware 啟動失敗: {e}")
        
        print("   ❌ 所有方法都失敗\n")
        return False

    def _release_busy(self):
        self._ir_busy = False

    def on_ir1_triggered(self):
        """IR1 觸發事件 - 5秒後執行檢測"""
        # 防止重入
        if getattr(self, "_ir_busy", False):
            self.log_message("[IR] IR1 ignored: busy")
            return
        self._ir_busy = True

        self.log_message("[IR] 🎯 IR1 觸發! 準備拍照...")

        # 1) 立即停輸送帶
        if not self._conv_off():
            self.log_message("[IR] ❌ 無法停止輸送帶")
            QTimer.singleShot(300, self._release_busy)
            return
        
        self.log_message("[IR] 🛑 輸送帶已停止")
        
        # 2) 5秒倒數後拍照
        def countdown_and_capture():
            """倒數計時並拍照"""
            self.log_message("[IR] ⏱️  5秒後開始拍照...")
            
            # 使用 QTimer 進行 5 秒延遲
            QTimer.singleShot(5000, perform_detection)
        
        def perform_detection():
            """執行拍照與檢測"""
            self.log_message("[IR] 📷 開始拍照...")
            
            # 拍照
            frame = None
            try:
                if hasattr(self.hardware, "get_camera_frame"):
                    frame = self.hardware.get_camera_frame()
            except Exception as e:
                self.log_message(f"[IR] ❌ get_camera_frame error: {e}")

            if frame is None:
                self.log_message("[IR] ❌ 無法取得相機影像")
                restart_conveyor()
                return

            # 辨識
            try:
                self.log_message("[IR] 🔍 開始 YOLO 辨識...")
                self.execute_detection()
                
                # 顯示結果
                if self.last_detection_result:
                    defects_str = ", ".join(self.last_defect_list) if self.last_defect_list else "無"
                    self.log_message(
                        f"[IR] ✅ 辨識完成: {self.last_detection_result} "
                        f"(缺陷: {defects_str})"
                    )
                else:
                    self.log_message("[IR] ⚠️ 辨識完成: 無結果")
                    
            except Exception as e:
                self.last_detection_result = None
                self.log_message(f"[IR] ❌ 辨識錯誤: {e}")
                import traceback
                traceback.print_exc()
            
            # 3秒後重啟輸送帶
            self.log_message("[IR] ⏱️  3秒後重啟輸送帶...")
            QTimer.singleShot(3000, restart_conveyor)
        
        def restart_conveyor():
            """重啟輸送帶並解鎖"""
            self._conv_on()
            self._release_busy()
            self.log_message("[IR] ✅ IR1 週期完成，系統就緒")
        
        # 啟動倒數
        countdown_and_capture()

    def _release_busy(self):
        """釋放 IR1 忙碌標誌"""
        self._ir_busy = False

    def on_ir2_triggered(self):
        """IR2 觸發事件 - 執行三分類（無缺陷不啟動機械手臂，直接輸送帶通過）"""
        # IR2 不跟 IR1 共用 busy
        if getattr(self, "_ir2_busy", False):
            self.log_message("[IR] IR2 ignored: busy")
            return
        self._ir2_busy = True

        # 1) 停輸送帶
        if not self._conv_off():
            self.log_message("[IR] ❌ 無法停止輸送帶")
            QTimer.singleShot(300, lambda: setattr(self, "_ir2_busy", False))
            return
            
        # 2) 根據上一片結果分類
        r = getattr(self, "last_detection_result", None)
        defects = getattr(self, "last_defect_list", None) or []
        num_defects = len(defects)

        # Case 1：IR2 來了但沒有辨識結果 → 直通（避免誤判 multiple）
        if r is None:
            self.log_message("[IR] ✅ IR2: 無上一片辨識結果，視為直通（不啟動機械手臂）")
            QTimer.singleShot(800, lambda: (self._conv_on(), setattr(self, "_ir2_busy", False)))
            return

        # Case 2：明確合格 / 無缺陷 → 直通
        if r in ("合格", "無缺陷") or num_defects == 0:
            self.log_message(f"[IR] ✅ IR2: 無缺陷直通（結果: {r}），不啟動機械手臂")
            QTimer.singleShot(800, lambda: (self._conv_on(), setattr(self, "_ir2_busy", False)))
            return

        # Case 3：有缺陷才分類
        if r == "單一缺陷":
            target = "single"
        elif r == "兩種缺陷":
            target = "double"
        else:
            target = "multiple"
        
        # 3) 執行機械手臂分類
        arm = None
        try:
            # 優先使用 arm_controller
            if hasattr(self, 'arm_controller') and self.arm_controller:
                arm = self.arm_controller
            # 其次使用 robotic_arm_controller
            elif hasattr(self, 'robotic_arm_controller') and self.robotic_arm_controller:
                arm = self.robotic_arm_controller
            # 最後檢查 hardware 中的機械手臂
            elif hasattr(self.hardware, 'robotic_arm') and self.hardware.robotic_arm:
                arm = self.hardware.robotic_arm

            if arm is None:
                self.log_message("[IR] ⚠️ 機械手臂未連接，跳過分類動作")
                self.log_message(f"[IR] 💡 檢測結果: {target}")
            else:
                self.log_message(f"[IR] 🤖 IR2 開始分類: {target}")

                if target == "single":
                    if hasattr(arm, 'move_to_single'):
                        arm.move_to_single()
                    elif hasattr(arm, 'execute_pick_and_place_sequence'):
                        arm.execute_pick_and_place_sequence('single')
                    elif hasattr(arm, 'move_to_predefined'):
                        arm.move_to_predefined('single_defect_area')
                    else:
                        self.log_message("[IR] ⚠️ 機械手臂不支援 single 動作")

                elif target == "double":
                    if hasattr(arm, 'move_to_double'):
                        arm.move_to_double()
                    elif hasattr(arm, 'execute_pick_and_place_sequence'):
                        arm.execute_pick_and_place_sequence('double')
                    elif hasattr(arm, 'move_to_predefined'):
                        arm.move_to_predefined('double_defect_area')
                    else:
                        self.log_message("[IR] ⚠️ 機械手臂不支援 double 動作")

                else:  # multiple
                    if hasattr(arm, 'move_to_multiple'):
                        arm.move_to_multiple()
                    elif hasattr(arm, 'execute_pick_and_place_sequence'):
                        arm.execute_pick_and_place_sequence('multiple')
                    elif hasattr(arm, 'move_to_predefined'):
                        arm.move_to_predefined('multiple_defect_area')
                    else:
                        self.log_message("[IR] ⚠️ 機械手臂不支援 multiple 動作")

                self.log_message(f"[IR] ✅ IR2 分類完成: {target}")

        except Exception as e:
            self.log_message(f"[IR] ❌ arm move error: {e}")
            import traceback
            traceback.print_exc()

        # 4) 延時後啟動輸送帶解鎖
        # 如果有機械手臂動作，等待較長時間；否則短時間
        delay_ms = 15000 if arm else 3000
        QTimer.singleShot(delay_ms, lambda: (self._conv_on(), setattr(self, "_ir2_busy", False)))



    
    def execute_detection(self):
        """執行一次拍照 + 檢測 (手動按鈕 / IR1 都會呼叫這個)"""
        try:
            # 1️從相機拿當前畫面（手動辨識 & IR1 共同使用）
            frame = self.hardware.get_camera_frame()
            if frame is None:
                print("⚠️ 無法獲取影像")
                return

            # 2️有模型 → 跑 YOLO + 三分類邏輯
            if self.image_processor is not None:
                edges, processed, detections = self.image_processor.process_frame(frame)

                # 顯示「有框的圖」到 YOLOV12 檢測結果區
                self.update_detection_display(processed)

                # 分析結果（只把非 pcb / normal 視為缺陷）
                defect_types = set()
                max_confidence = 0.0

                for det in detections:
                    if det.class_name not in ["pcb", "normal"]:
                        defect_types.add(det.class_name)
                        if det.confidence > max_confidence:
                            max_confidence = det.confidence

                # 給 IR2 用的狀態
                self.last_defect_list = list(defect_types)
                self.last_detection_image = processed

                # 三分類結果
                num_defect_types = len(defect_types)
                if num_defect_types == 0:
                    self.last_detection_result = "合格"
                    classification = "無缺陷"
                elif num_defect_types == 1:
                    self.last_detection_result = "單一缺陷"
                    classification = "🔵 單一缺陷"
                elif num_defect_types == 2:
                    self.last_detection_result = "兩種缺陷"
                    classification = "🟡 兩種缺陷"
                else:
                    self.last_detection_result = "多種缺陷"
                    classification = "🔴 多種缺陷"

                defect_str = ",".join(defect_types) if defect_types else "-"
                self.add_detection_record(
                    self.last_detection_result,
                    defect_str,
                    classification,
                    max_confidence,
                )

                print(f"📊 檢測結果: {self.last_detection_result} ({defect_str})")

            else:
                # 3️沒有模型 → 只顯示原始畫面在 YOLOV12 檢測結果區
                self.update_detection_display(frame)
                self.last_detection_result = None
                self.last_defect_list = []
                self.last_detection_image = frame
                print("ℹ️ 未載入模型，只顯示原始畫面。")

        except Exception as e:
            print(f"❌ 檢測錯誤: {e}")
            import traceback
            traceback.print_exc()



    
    def execute_three_class_sorting(self):
        """執行三分類分類"""
        if not self.last_detection_result:
            return
        
        try:
            # 根據缺陷數量決定分類
            num_defects = len(self.last_defect_list)
            
            if num_defects == 0:
                # 合格品，不分類
                print("✅ 合格品，無需分類")
                return
            elif num_defects == 1:
                target = 'single'
            elif num_defects == 2:
                target = 'double'
            else:
                target = 'multiple'
            
            # 執行分類
            if self.arm_controller:
                success = self.arm_controller.execute_pick_and_place_sequence(target)
                if success:
                    print(f"✅ 三分類完成: {target}")
                else:
                    print(f"❌ 三分類失敗: {target}")
            elif hasattr(self.hardware, 'robotic_arm') and self.hardware.robotic_arm:
                self.hardware.robotic_arm.execute_pick_and_place_sequence(target)
            else:
                print(f"🔄 模擬三分類: {target}")
                
        except Exception as e:
            print(f"❌ 分類錯誤: {e}")
    
    def add_detection_record(self, result, defect_type, classification, confidence):
        """添加檢測記錄"""
        # 更新統計
        self.data_manager.add_record(result, defect_type, confidence)
        
        # 添加到表格
        row = self.log_table.rowCount()
        self.log_table.insertRow(row)
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        items = [
            timestamp,
            result,
            defect_type,
            classification,
            f"{confidence:.2f}",
            "自動檢測"
        ]
        
        for col, text in enumerate(items):
            item = QTableWidgetItem(str(text))
            item.setTextAlignment(Qt.AlignCenter)
            
            # 根據分類設置顏色
            if "單一" in classification:
                item.setBackground(QColor("#E3F2FD"))
            elif "兩種" in classification:
                item.setBackground(QColor("#FFF3E0"))
            elif "多種" in classification:
                item.setBackground(QColor("#FFEBEE"))
            
            self.log_table.setItem(row, col, item)
        
        self.log_table.scrollToBottom()
        self.update_statistics_display()
    
    @pyqtSlot(np.ndarray)
    def update_camera_display(self, frame):
        """更新相機顯示"""
        if frame is not None:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            
            pixmap = QPixmap.fromImage(qt_image)
            scaled_pixmap = pixmap.scaled(
                self.original_image_display.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.original_image_display.setPixmap(scaled_pixmap)
    
    def update_detection_display(self, frame):
        """更新檢測結果顯示"""
        if frame is not None:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            
            pixmap = QPixmap.fromImage(qt_image)
            scaled_pixmap = pixmap.scaled(
                self.detection_image_display.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.detection_image_display.setPixmap(scaled_pixmap)
    
    def update_conveyor_speed(self, value):
        """更新輸送帶速度"""
        self.speed_label.setText(f"輸送帶速度: {value}%")
        self.hardware.set_conveyor_speed(value)
    
    def update_threshold(self, value):
        """更新檢測閾值"""
        threshold = value / 100.0
        self.threshold_label.setText(f"檢測閾值: {threshold:.2f}")
        
        if self.image_processor:
            self.image_processor.update_config(yolo_confidence=threshold)
    
    def update_servo_angle(self, value):
        """更新伺服角度 (已停用硬體輸出)"""
        if hasattr(self, "servo_label"):
            self.servo_label.setText(f"伺服角度: {value}°")
        # 不呼叫硬體，避免干擾現有機械手臂
        
    
    def choose_model_file(self):
        """手動選擇 YOLO 模型檔並重新載入"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "選擇 YOLO 模型權重檔",
            "",
            "YOLO 模型 (*.pt *.onnx);;所有檔案 (*.*)"
        )

        # 使用者按取消
        if not file_path:
            return

        try:
            # 紀錄目前模型路徑
            self.current_model_path = file_path
            model_file_name = os.path.basename(file_path)

            # 類別定義要跟訓練的模型一致（三類：鼠咬 / 斷路 / 雜銅）
            custom_classes = {
                0: '鼠咬',
                1: '斷路',
                2: '雜銅'
            }

            # 重新建立影像處理器
            self.image_processor = ImageProcessor(
                model_path=self.current_model_path,
                class_names=custom_classes
            )

            QMessageBox.information(
                self,
                "模型載入成功",
                f"已載入模型：\n{model_file_name}"
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "模型載入失敗",
                f"載入模型時發生錯誤：\n{e}"
            )
            self.image_processor = None

        # 右邊模型狀態 / 模型資訊顯示
        self.update_status_displays()



    def switch_camera(self):
        """切換相機"""
        index = self.camera_index_spin.value()
        
        try:
            old_index = self.hardware.camera_index
            self.hardware.camera_index = index
            
            # 重新初始化相機
            if hasattr(self.hardware, 'init_camera'):
                success = self.hardware.init_camera()
            elif hasattr(self.hardware, 'init_hardware'):
                success = self.hardware.init_hardware()
            else:
                success = False
            
            if success:
                QMessageBox.information(
                    self, 
                    "成功", 
                    f"已切換相機: {old_index} → {index}"
                )
                print(f"✅ 相機已切換: index {old_index} → {index}")
            else:
                # 切換失敗,還原設定
                self.hardware.camera_index = old_index
                QMessageBox.warning(
                    self, 
                    "失敗", 
                    f"無法切換到相機 {index}\n可能該索引無可用相機"
                )
                print(f"⚠️ 相機切換失敗: index {index}")
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "錯誤",
                f"切換相機時發生錯誤:\n{e}"
            )
            print(f"❌ 相機切換錯誤: {e}")
    
    def reset_system(self):
        """重設系統"""
        # 停止所有運作
        if self.conveyor_running:
            self.toggle_conveyor()
        
        if self.ir1_detection_enabled:
            self.toggle_ir1_detection()
        
        if self.ir2_detection_enabled:
            self.toggle_ir2_detection()
        
          # 重設滑桿
        self.speed_slider.setValue(50)
        self.threshold_slider.setValue(50)
        # 伺服角度功能已停用，不再重設或輸出
        
        # 更新顯示
        self.update_conveyor_speed(50)
        self.update_threshold(50)
        # self.update_servo_angle(90)  # 可省略

        
        # 清除上次檢測結果
        self.last_detection_result = None
        self.last_defect_list = []
        
        print("🔄 系統已重設")
        QMessageBox.information(self, "系統重設", "系統已重設到初始狀態")
    
    def update_status_displays(self):
        """更新狀態顯示"""
        hardware_status = self.hardware.get_hardware_status()
        
        # 相機狀態
        if hardware_status.get('camera_available', False):
            self.camera_status.setText("相機狀態: 🟢 正常")
        else:
            self.camera_status.setText("相機狀態: 🔴 離線")
        
        # 分類系統 / 機械手臂狀態
        arm = getattr(self, "arm_controller", None)
        if arm and getattr(arm, "is_connected", False):
            self.servo_status.setText("分類系統: 🤖 六軸機械手臂就緒")
        elif hasattr(self.hardware, 'robotic_arm') and self.hardware.robotic_arm:
            arm_status = self.hardware.get_arm_status()
            if arm_status.get('hardware_available', False):
                self.servo_status.setText("分類系統: 🤖 六軸機械手臂就緒")
            else:
                self.servo_status.setText("分類系統: 🤖 六軸機械手臂(模擬模式)")
        
        
        # 模型狀態 & 模型資訊
        if self.image_processor:
            stats = self.image_processor.get_processing_stats()  
            
            # 狀態文字
            model_status = "✅ 模型就緒" if stats.get('yolo_available', False) else "⚠️ 模型未載入"
            self.model_status_label.setText(f"模型狀態: {model_status}")
            
            # 如果模型已載入，顯示詳細資訊
            if stats.get('yolo_available', False):
                # 模型檔名
                model_path = stats.get('model_path') or self.current_model_path
                model_name = os.path.basename(model_path) if model_path else "未知模型"
                
                # 類別數 / 類別名稱
                num_classes = stats.get('num_classes', 0)
                
                # ImageProcessor 裡 pcb_classes 目前是 dict: {id: name}
                class_names = []
                if hasattr(self.image_processor, "pcb_classes"):
                    if isinstance(self.image_processor.pcb_classes, dict):
                        # dict = 取 values，再去重
                        class_names = sorted(list(set(self.image_processor.pcb_classes.values())))
                    else:
                        # 如果是 list，就當作 list 用
                        class_names = list(self.image_processor.pcb_classes)
                
                class_names_str = ", ".join(class_names) if class_names else "-"
                
                self.model_info_label.setText(
                    f"模型: {model_name} ({num_classes} 類)\n"
                    f"類別: {class_names_str}"
                )
            else:
                # 模型存在 image_processor，但 YOLO 還沒載入成功
                self.model_info_label.setText("模型資訊: -")
        else:
            # 未建立 image_processor
            self.model_status_label.setText("模型狀態: ⚠️ 尚未初始化")
            self.model_info_label.setText("模型資訊: -")
        
        # 更新統計數據顯示（總檢測數 / 合格率 / 三分類）
        self.update_statistics_display()

    
    def update_statistics_display(self):
        """更新統計數據顯示"""
        stats = self.data_manager.get_statistics()
        
        # 基本統計
        self.total_label.setText(f"總檢測數: {getattr(stats, 'total_count', 0)}")
        self.pass_label.setText(f"合格數: {getattr(stats, 'pass_count', 0)}")
        self.defect_label.setText(f"缺陷數: {getattr(stats, 'defect_count', 0)}")
        
        # 合格率
        if hasattr(stats, "get_pass_rate"):
            pass_rate = stats.get_pass_rate()
        else:
            total = float(getattr(stats, "total_count", 0))
            passed = float(getattr(stats, "pass_count", 0))
            pass_rate = (passed / total * 100.0) if total > 0 else 0.0
        self.pass_rate_label.setText(f"合格率: {pass_rate:.1f}%")
        
        # 三分類統計
        if hasattr(stats, "get_classification_distribution"):
            class_dist = stats.get_classification_distribution()
        else:
            class_dist = {
                "單一缺陷": getattr(stats, "single_defect_count", 0),
                "兩種缺陷": getattr(stats, "double_defect_count", 0),
                "多種缺陷": getattr(stats, "multiple_defect_count", 0),
            }
        
        self.single_defect_label.setText(f"🔵 單一缺陷: {class_dist.get('單一缺陷', 0)}")
        self.double_defect_label.setText(f"🟡 兩種缺陷: {class_dist.get('兩種缺陷', 0)}")
        self.multiple_defect_label.setText(f"🔴 多種缺陷: {class_dist.get('多種缺陷', 0)}")
    
    def export_txt_report(self):
        """匯出TXT報告"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "匯出TXT報告",
                f"PCB_Defect_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                "文字檔案 (*.txt)"
            )
            
            if file_path:
                saved_path = self.data_manager.export_report(file_path)
                if saved_path:
                    QMessageBox.information(self, "匯出成功", f"報告已匯出至: {saved_path}")
                else:
                    QMessageBox.warning(self, "匯出失敗", "匯出報告時發生錯誤")
        
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"匯出報告時發生錯誤: {str(e)}")
    
    def export_csv_data(self):
        """匯出CSV數據"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "匯出CSV數據",
                f"PCB_Defect_Data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "CSV檔案 (*.csv)"
            )
            
            if file_path:
                saved_path = self.data_manager.export_csv(file_path)
                if saved_path:
                    QMessageBox.information(self, "匯出成功", f"數據已匯出至: {saved_path}")
                else:
                    QMessageBox.warning(self, "匯出失敗", "匯出數據時發生錯誤")
        
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"匯出數據時發生錯誤: {str(e)}")
    
    def clear_records(self):
        """清除記錄"""
        reply = QMessageBox.question(
            self, "清除記錄", "確定要清除所有記錄嗎?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.data_manager.clear_records()
            self.log_table.setRowCount(0)
            self.update_statistics_display()
            QMessageBox.information(self, "清除完成", "所有記錄已清除")
    
    def closeEvent(self, event):
        """程序關閉事件"""
        print("🔄 正在關閉系統...")
        
        # 關閉IR檢測
        if self.ir1_detection_enabled:
            self.ir1_detection_enabled = False
            self.ir1_status.setText("IR1狀態: 🔴 關閉")
        
        if self.ir2_detection_enabled:
            self.ir2_detection_enabled = False
            self.ir2_status.setText("IR2狀態: 🔴 關閉")
        
        # 停止輸送帶
        if self.conveyor_running:
            self.toggle_conveyor()
        
        # 關閉機械手臂控制視窗
        if self.arm_control_window:
            self.arm_control_window.close()
        
        # 停止線程
        if self.camera_thread and self.camera_thread.isRunning():
            self.camera_thread.stop()
            self.camera_thread.wait(3000)
        
        if getattr(self, 'ir1_sensor_thread', None):
            if self.ir1_sensor_thread.isRunning():
                self.ir1_sensor_thread.stop()
                self.ir1_sensor_thread.wait(3000)
        
        thr = getattr(self, 'ir2_sensor_thread', None)
        if thr and thr.isRunning():
            thr.stop()
            thr.wait(3000)

        
        # 清理硬體
        try:
            self.hardware.cleanup()
        except Exception as e:
            print(f"⚠️ 清理硬體時發生錯誤: {e}")
        
        # 清理機械手臂控制器
        if self.arm_controller:
            try:
                self.arm_controller.cleanup()
            except Exception as e:
                print(f"⚠️ 清理機械手臂時發生錯誤: {e}")
        
        print("✅ 系統已安全關閉")
        event.accept()


def main():
    """主程序入口"""
    app = QApplication(sys.argv)
    
    app.setStyle('Fusion')
    font = QFont("Microsoft JhengHei", 9)
    app.setFont(font)
    
    # 檢查硬體環境
    try:
        from hardware_controller import GPIO_AVAILABLE
        if not GPIO_AVAILABLE:
            print("⚠️ 警告: GPIO模組未安裝,程序將以模擬模式運行")
    except ImportError:
        print("⚠️ 無法導入硬體控制模組")
    
    # 創建並顯示主視窗
    try:
        window = PCBADetectionSystem()
        window.show()
        
        print("🚀 PCB缺陷檢測系統已啟動 v4.0")
        print("📋 檢測項目: 🐭鼠咬 ⚡斷路 🔶雜銅")
        print("🎨 分類模式: 三分類系統")
        print("\n💡 使用說明:")
        print("   1. 點擊「啟用IR1自動檢測」開始自動檢測模式")
        print("   2. 當PCB經過IR1感應器時,系統自動拍照並檢測")
        print("   3. 點擊「啟用IR2自動分類」啟用自動分類")
        print("   4. 當PCB經過IR2感應器時,根據檢測結果自動三分類")
        print("   5. 點擊「🤖 機械手臂控制」開啟獨立控制介面")
        print("\n🎨 三分類說明:")
        print("   🔵 單一缺陷: 檢測到1種缺陷類型")
        print("   🟡 兩種缺陷: 檢測到2種缺陷類型")
        print("   🔴 多種缺陷: 檢測到3種及以上缺陷類型")
        
        sys.exit(app.exec_())
        
    except Exception as e:
        print(f"❌ 程序啟動失敗: {e}")
        import traceback
        traceback.print_exc()
        QMessageBox.critical(None, "啟動錯誤", f"程序啟動失敗: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()