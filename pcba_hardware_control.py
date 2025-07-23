import sys
import os
import cv2
import time
import threading
import numpy as np
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QGridLayout, QPushButton, QLabel, 
                            QSlider, QTableWidget, QTableWidgetItem, QGroupBox,
                            QFrame, QScrollArea, QSplitter, QMessageBox)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot
from PyQt5.QtGui import QFont, QPalette, QColor, QPixmap, QPainter, QImage
from PyQt5.QtMultimedia import QSound

# 硬體控制模組
try:
    import Jetson.GPIO as GPIO
    import board
    import busio
    from adafruit_pca9685 import PCA9685
    from adafruit_motor import servo
    GPIO_AVAILABLE = True
except ImportError:
    print("GPIO模組未安裝，將使用模擬模式")
    GPIO_AVAILABLE = False

class HardwareController:
    """硬體控制器類"""
    
    def __init__(self):
        self.gpio_available = GPIO_AVAILABLE
        self.camera = None
        self.pca = None
        self.servos = []
        self.encoders = []  # 保存 KY-040 每組 encoder 的 GPIO 設定
        self.encoder_values = [0, 0, 0]  # 編碼器計數器
        self.init_hardware()
        
    def init_hardware(self):
        """初始化硬體設備"""
        if self.gpio_available:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setwarnings(False)
                
                # 初始化 I2C -> PCA9685
                i2c = busio.I2C(board.SCL, board.SDA)
                self.pca = PCA9685(i2c)
                self.pca.frequency = 50

                # 初始化 6 顆 MG996R 伺服馬達 (PCA9685 channel 0~5)
                for ch in range(6):
                    self.servos.append(servo.Servo(self.pca.channels[ch]))
                
                print("✅ 伺服馬達初始化完成")
                
                # 初始化 KY-040 編碼器 3 組
                encoder_pins = [
                    {"clk": 17, "dt": 18, "sw": 27},  # #1 - GPIO11,12,13
                    {"clk": 22, "dt": 23, "sw": 24},  # #2 - GPIO15,16,18
                    {"clk": 25, "dt": 4, "sw": 5}     # #3 - GPIO22,7,29
                ]

                for idx, pins in enumerate(encoder_pins):
                    GPIO.setup(pins["clk"], GPIO.IN, pull_up_down=GPIO.PUD_UP)
                    GPIO.setup(pins["dt"], GPIO.IN, pull_up_down=GPIO.PUD_UP)
                    GPIO.setup(pins["sw"], GPIO.IN, pull_up_down=GPIO.PUD_UP)
                    self.encoders.append(pins)
                
                print("✅ KY-040 編碼器初始化完成")

            except Exception as e:
                print(f"❌ 硬體初始化失敗: {e}")
                self.gpio_available = False

        # 初始化相機
        self.init_camera()
    
    def init_camera(self):
        """初始化相機"""
        try:
            self.camera = cv2.VideoCapture(0)
            if self.camera.isOpened():
                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                self.camera.set(cv2.CAP_PROP_FPS, 30)
                print("📷 相機初始化成功")
            else:
                self.camera = None
        except Exception as e:
            print(f"相機初始化錯誤: {e}")
            self.camera = None
    
    def get_camera_frame(self):
        """獲取相機畫面"""
        if self.camera and self.camera.isOpened():
            ret, frame = self.camera.read()
            if ret:
                return frame
        return None

    def set_servo_angle(self, index, angle):
        """控制第 index 顆伺服馬達的角度"""
        if not self.gpio_available:
            print(f"模擬模式：Servo {index} 設定角度 {angle}°")
            return
        
        try:
            angle = max(0, min(180, angle))
            if 0 <= index < len(self.servos):
                self.servos[index].angle = angle
        except Exception as e:
            print(f"伺服馬達控制錯誤: {e}")

    def read_encoder(self, index):
        """讀取指定 KY-040 編碼器的方向變化（簡化）"""
        if not self.gpio_available:
            import random
            return random.choice([-1, 0, 1])  # 模擬模式
        try:
            pins = self.encoders[index]
            clk = GPIO.input(pins["clk"])
            dt = GPIO.input(pins["dt"])
            if clk == 0 and dt == 1:
                return 1  # 正轉
            elif clk == 0 and dt == 0:
                return -1  # 反轉
            else:
                return 0
        except Exception as e:
            print(f"讀取編碼器錯誤: {e}")
            return 0

    def cleanup(self):
        """清理硬體資源"""
        if self.camera:
            self.camera.release()
        if self.gpio_available:
            try:
                if self.pca:
                    self.pca.deinit()
                GPIO.cleanup()
            except Exception as e:
                print(f"硬體清理錯誤: {e}")


class CameraThread(QThread):
    """相機線程"""
    frame_ready = pyqtSignal(np.ndarray)
    
    def __init__(self, hardware_controller):
        super().__init__()
        self.hardware = hardware_controller
        self.running = False
    
    def run(self):
        """線程運行"""
        self.running = True
        while self.running:
            frame = self.hardware.get_camera_frame()
            if frame is not None:
                self.frame_ready.emit(frame)
            time.sleep(0.033)  # ~30 FPS
    
    def stop(self):
        """停止線程"""
        self.running = False
        self.quit()
        self.wait()

class DetectionThread(QThread):
    """檢測線程"""
    detection_result = pyqtSignal(str, str)  # result, defect_type
    
    def __init__(self, hardware_controller):
        super().__init__()
        self.hardware = hardware_controller
        self.running = False
        self.threshold = 0.8
    
    def run(self):
        """運行檢測邏輯"""
        self.running = True
        while self.running:
            # 檢查感測器是否檢測到物體
            if self.hardware.read_sensor():
                # 獲取相機畫面進行檢測
                frame = self.hardware.get_camera_frame()
                if frame is not None:
                    result, defect = self.detect_pcba(frame)
                    self.detection_result.emit(result, defect)
                    
                    # 根據結果控制伺服馬達和輸送帶
                    if result == "合格":
                        self.hardware.set_servo_angle(45)  # 合格品分類角度
                        time.sleep(0.5)
                        self.hardware.set_servo_angle(90)  # 復位
                    else:
                        self.hardware.set_servo_angle(135)  # 不良品分類角度
                        time.sleep(0.5)
                        self.hardware.set_servo_angle(90)  # 復位
                
                time.sleep(1)  # 避免重複檢測
            
            time.sleep(0.1)
    
    def detect_pcba(self, frame):
        """PCBA檢測邏輯（簡化版本）"""
        # 這裡可以加入實際的AI檢測邏輯
        # 目前使用簡化的檢測邏輯作為示例
        
        import random
        
        # 模擬檢測結果
        defect_types = ["短路", "斷路", "橋接", "缺件"]
        
        # 基於閾值和隨機因素決定檢測結果
        detection_score = random.random()
        
        if detection_score > self.threshold:
            return "合格", ""
        else:
            defect_type = random.choice(defect_types)
            return "缺陷", defect_type
    
    def set_threshold(self, threshold):
        """設置檢測閾值"""
        self.threshold = threshold
    
    def stop(self):
        """停止檢測"""
        self.running = False
        self.quit()
        self.wait()

from pcba_ui import PCBADetectionSystem

def main():
    app = QApplication(sys.argv)
    
    # 設置應用程式樣式
    app.setStyle('Fusion')
    
    # 設置字體
    font = QFont("Microsoft JhengHei", 9)
    app.setFont(font)
    
    # 檢查硬體環境
    if not GPIO_AVAILABLE:
        print("警告：GPIO模組未安裝，程序將以模擬模式運行")
        print("若要使用實際硬體，請安裝以下模組：")
        print("- Jetson.GPIO")
        print("- adafruit-circuitpython-pca9685")
        print("- adafruit-circuitpython-motor")
    
    hardware = HardwareController()
    camera_thread = CameraThread(hardware)
    detection_thread = DetectionThread(hardware)
    # UI 與邏輯分離
    window = PCBADetectionSystem(hardware, camera_thread, detection_thread)
    # 設定 UI 與邏輯的連結
    window.start_btn.clicked.connect(window.start_auto_detection)
    window.stop_btn.clicked.connect(window.stop_auto_detection)
    window.servo_slider.valueChanged.connect(window.update_servo)
    window.speed_slider.valueChanged.connect(window.update_conveyor_speed)
    window.threshold_slider.valueChanged.connect(window.update_threshold)
    window.conveyor_btn.clicked.connect(window.toggle_conveyor)
    window.reset_btn.clicked.connect(window.reset_system)
    window.relay_btn.clicked.connect(window.toggle_relay)
    # 匯出/清除按鈕
    # 需在 UI class 內 expose 這些按鈕
    # window.export_btn.clicked.connect(window.export_report)
    # window.clear_btn.clicked.connect(window.clear_records)
    # 設定相機與檢測線程的訊號連結
    camera_thread.frame_ready.connect(window.update_camera_display)
    detection_thread.detection_result.connect(window.handle_detection_result)
    window.show()
    
    try:
        sys.exit(app.exec_())
    except SystemExit:
        pass

if __name__ == '__main__':
    main()

# 安裝所需模組的指令：
# pip install PyQt5 opencv-python numpy
# pip install Jetson.GPIO  # 適用於 Jetson 平台
# pip install adafruit-circuitpython-pca9685
# pip install adafruit-circuitpython-motor

# 硬體連接說明：
"""
Jetson Orin Nano GPIO 連接：
- L298N 馬達驅動：
  - IN1 -> GPIO18
  - IN2 -> GPIO19
  - IN3 -> GPIO20
  - IN4 -> GPIO21
  - ENA -> GPIO12 (PWM)
  - ENB -> GPIO13 (PWM)
  
- TCRT5000 光電感測器：
  - VCC -> 3.3V
  - GND -> GND
  - OUT -> GPIO24
  
- 繼電器模組：
  - VCC -> 5V
  - GND -> GND
  - IN -> GPIO25
  
- PCA9685 模組 (I2C)：
  - VCC -> 3.3V
  - GND -> GND
  - SDA -> SDA (Pin 3)
  - SCL -> SCL (Pin 5)
  
- SG90 伺服馬達：
  - 紅線 -> 5V
  - 黑線 -> GND
  - 黃線 -> PCA9685 Channel 0
  
- USB 相機：
  - 直接連接到 USB 端口
  
- 輸送帶模組：
  - 透過 L298N 驅動直流馬達
"""