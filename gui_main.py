import sys
import os
import time
from datetime import datetime
import cv2
import torch
import numpy as np

from PyQt5.QtWidgets import QApplication, QMainWindow, QTableWidgetItem, QLabel
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import Qt, QThread, pyqtSignal

# 匯入我們的模組
from ui import PCBAUIInterface
from yolo_inference import YOLOv12Detector
from camera_capture import capture_image
from conveyor_control import ConveyorControl
from robot_arm_control import RobotArmControl

# ======================================================================
# --- 全局配置 ---
# ======================================================================
# --- 模型配置 ---
# !!! 請將您的 YOLOv12 .pt 檔案放在 'weights' 資料夾中 !!!
YOLO_WEIGHTS_PATH = "weights/best.pt"
# 自動檢測設備
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'

# --- 硬體配置 ---
# !!! 請根據您的硬體連接修改這些參數 !!!
# 'jetson_gpio' 或 'custom' (示意模式)
ARM_PWM_LIB_TYPE = "jetson_gpio"
# BCM 腳位號碼: [base, shoulder, elbow, wrist_pitch, wrist_roll, special]
ARM_JOINT_PINS = [17, 18, 27, 22, 23, 24]
ARM_GRIPPER_PIN = 25

# 'gpio', 'serial', 或 'custom' (示意模式)
CONVEYOR_CONTROL_TYPE = "gpio"
# 如果是 'gpio' 模式，設定 GPIO 腳位
CONVEYOR_GPIO_PINS = {'forward': 13, 'enable': 19, 'sensor': 26} # 範例腳位, 請替換
# 如果是 'serial' 模式，設定序列埠
CONVEYOR_SERIAL_PORT = '/dev/ttyUSB0' # or 'COM3' on Windows
CONVEYOR_BAUDRATE = 9600

# --- 邏輯配置 ---
# 產品類別到機械手臂放置區域的映射
# !!! 請根據您模型的類別名稱進行修改 !!!
PRODUCT_TO_ZONE_MAP = {
    "class_A": 1,
    "class_B": 2,
    "class_C": 3,
    "class_D": 4,
    "OK": 1,      # 假設 "OK" 產品放到區域 1
    "NG": 2,      # 假設 "NG" 產品放到區域 2
}
DEFAULT_ZONE_FOR_UNKNOWN = 0 # 0 代表廢料區或不做處理

# --- 影像前處理配置 ---
PREPROCESSING_ENABLED = True # 設定為 True 來啟用前處理
HIGH_BOOST_K = 1.5 # 高增幅濾波的 k 值

# ======================================================================
# --- 自動化流程工作線程 ---
# ======================================================================
class AutomationWorker(QThread):
    # --- 信號定義 ---
    status_updated = pyqtSignal(QLabel, str, str)
    image_updated = pyqtSignal(QPixmap)
    log_added = pyqtSignal(list)
    stats_updated = pyqtSignal(dict)
    finished = pyqtSignal()

    def __init__(self, detector, conveyor, robot_arm):
        super().__init__()
        self.detector = detector
        self.conveyor = conveyor
        self.robot_arm = robot_arm
        self.is_running = False
        self.stats = {'total': 0, 'pass': 0, 'defect': 0}

    def _preprocess_image(self, input_path):
        """對影像進行邊緣偵測和高增幅濾波"""
        try:
            self.log_event("影像前處理中...", "info")
            img = cv2.imread(input_path)
            if img is None:
                self.log_event(f"讀取影像失敗: {input_path}", "error")
                return input_path, False

            # 1. Canny 邊緣偵測 (主要用於視覺化或作為一個特徵)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 100, 200)

            # 2. 高增幅濾波 (High-Boost Filtering)
            # 創建一個模糊版本的影像
            blurred = cv2.GaussianBlur(img, (7, 7), 0)
            # 計算遮罩 (原始影像 - 模糊影像)
            mask = cv2.subtract(img, blurred)
            # 將遮罩加權後加回到原始影像
            high_boost_img = cv2.addWeighted(img, 1.0, mask, HIGH_BOOST_K, 0)

            # 建立儲存目錄
            output_dir = "processed_images"
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            # 儲存處理後的影像
            filename = os.path.basename(input_path)
            output_path = os.path.join(output_dir, f"processed_{filename}")
            cv2.imwrite(output_path, high_boost_img)

            self.log_event("影像前處理完成", "success")
            return output_path, True
        except Exception as e:
            self.log_event(f"影像前處理失敗: {e}", "error")
            return input_path, False

    def run(self):
        self.is_running = True
        while self.is_running:
            self.status_updated.emit(self.parent().ui.system_status, "系統狀態：🟢 運行中", "green")

            # --- 1. 等待產品 & 影像擷取 ---
            self.log_event("等待產品觸發...", "info")
            time.sleep(1) # 示意等待

            self.status_updated.emit(self.parent().ui.camera_status, "相機狀態：🟡 擷取中...", "orange")
            image_path = capture_image(output_dir="live_captured_images")
            if not image_path:
                self.log_event("影像擷取失敗", "error")
                self.status_updated.emit(self.parent().ui.camera_status, "相機狀態：🔴 失敗", "red")
                continue

            self.log_event(f"影像擷取成功: {os.path.basename(image_path)}", "info")
            self.status_updated.emit(self.parent().ui.camera_status, "相機狀態：🟢 正常", "green")

            # --- 2. 影像前處理 ---
            path_for_yolo = image_path
            if PREPROCESSING_ENABLED:
                processed_path, success = self._preprocess_image(image_path)
                if success:
                    path_for_yolo = processed_path

            # 更新 GUI 上的圖片
            self.update_display_image(path_for_yolo)

            # --- 3. YOLO 推論 ---
            self.log_event("YOLOv12 推論中...", "info")
            detections = self.detector.detect(path_for_yolo)
            self.stats['total'] += 1

            if not detections:
                self.log_event("未偵測到任何物件", "warning")
                self.stats['pass'] += 1 # 假設沒偵測到=良品
                self.update_stats_display()
                continue

            # --- 4. 處理偵測結果 ---
            best_detection = detections[0]
            label = best_detection['label']
            confidence = best_detection['confidence']
            self.log_event(f"偵測到: {label} (信心度: {confidence:.2f})", "success")
            self.draw_detections_on_image(path_for_yolo, detections)

            # --- 5. 決策與硬體控制 ---
            target_zone = PRODUCT_TO_ZONE_MAP.get(label, DEFAULT_ZONE_FOR_UNKNOWN)
            if target_zone == 0:
                self.log_event(f"未知類別 '{label}'，移至廢料區", "warning")
                self.stats['defect'] += 1
            else:
                self.log_event(f"產品 '{label}'，移至區域 {target_zone}", "info")
                self.stats['pass'] += 1

            # --- 6. 輸送帶移動 ---
            self.status_updated.emit(self.parent().ui.conveyor_status, "輸送帶狀態：🟡 移動中...", "orange")
            if self.conveyor.move_to_pickup_point():
                self.log_event("產品已到達夾取點", "info")
                self.status_updated.emit(self.parent().ui.conveyor_status, "輸送帶狀態：🟢 停止", "green")
            else:
                self.log_event("產品移動失敗", "error")
                self.status_updated.emit(self.parent().ui.conveyor_status, "輸送帶狀態：🔴 錯誤", "red")
                continue

            # --- 7. 機械手臂動作 ---
            self.status_updated.emit(self.parent().ui.servo_status, "伺服控制：🟡 動作中...", "orange")
            self.robot_arm.pickup_object()
            self.robot_arm.place_object_in_zone(target_zone)
            self.status_updated.emit(self.parent().ui.servo_status, "伺服控制：🟢 就緒", "green")

            self.update_stats_display()
            time.sleep(2)

        self.finished.emit()

    def stop(self):
        self.is_running = False

    def log_event(self, message, level):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_map = {"info": "訊息", "success": "成功", "warning": "警告", "error": "錯誤"}
        self.log_added.emit([timestamp, log_map.get(level, "未知"), message, ""])

    def update_display_image(self, image_path):
        pixmap = QPixmap(image_path)
        self.image_updated.emit(pixmap)

    def draw_detections_on_image(self, image_path, detections):
        img = cv2.imread(image_path)
        for det in detections:
            label, confidence, bbox = det['label'], det['confidence'], det['bbox']
            x1, y1, x2, y2 = bbox
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(img, f"{label} {confidence:.2f}", (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

        rgb_image = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        qt_image = QImage(rgb_image.data, w, h, ch * w, QImage.Format_RGB888)
        self.image_updated.emit(QPixmap.fromImage(qt_image))

    def update_stats_display(self):
        self.stats['rate'] = (self.stats['pass'] / self.stats['total'] * 100) if self.stats['total'] > 0 else 0
        self.stats_updated.emit(self.stats)

# ======================================================================
# --- 主視窗 ---
# ======================================================================
class PCBAMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = PCBAUIInterface(self)
        self.init_modules()
        self.ui.connect_signals(self)
        self.is_conveyor_on = False

    def init_modules(self):
        self.update_status_label(self.ui.system_status, "系統狀態：🟡 初始化中...", "orange")

        if not os.path.exists(YOLO_WEIGHTS_PATH):
            self.update_status_label(self.ui.system_status, f"系統狀態：🔴 錯誤 - 找不到模型", "red")
            self.detector = None
        else:
            self.detector = YOLOv12Detector(weights_path=YOLO_WEIGHTS_PATH, device=DEVICE)

        self.conveyor = ConveyorControl(port=CONVEYOR_SERIAL_PORT, baudrate=CONVEYOR_BAUDRATE,
                                     control_pins=CONVEYOR_GPIO_PINS, control_type=CONVEYOR_CONTROL_TYPE)
        self.conveyor.connect()

        self.robot_arm = RobotArmControl(joint_pins=ARM_JOINT_PINS, gripper_pin=ARM_GRIPPER_PIN,
                                       pwm_lib_type=ARM_PWM_LIB_TYPE)

        self.worker = AutomationWorker(self.detector, self.conveyor, self.robot_arm)
        self.worker.setParent(self)
        self.worker.status_updated.connect(self.update_status_label)
        self.worker.image_updated.connect(self.update_image_display)
        self.worker.log_added.connect(self.add_log_entry)
        self.worker.stats_updated.connect(self.update_stats)
        self.worker.finished.connect(self.on_worker_finished)

        self.update_status_label(self.ui.system_status, "系統狀態：🟢 就緒", "green")
        print("所有模組初始化完成。")

    def start_auto_detection(self):
        if self.detector is None:
            print("無法啟動，YOLO 模型未載入。")
            return
        if not self.worker.isRunning():
            self.ui.start_btn.setEnabled(False)
            self.ui.stop_btn.setEnabled(True)
            self.worker.start()

    def stop_auto_detection(self):
        if self.worker.isRunning():
            self.worker.stop()
            self.update_status_label(self.ui.system_status, "系統狀態：🟡 停止中...", "orange")

    def on_worker_finished(self):
        self.ui.start_btn.setEnabled(True)
        self.ui.stop_btn.setEnabled(False)
        self.update_status_label(self.ui.system_status, "系統狀態：🔴 停止", "red")
        self.conveyor.stop()
        self.robot_arm.move_to_named_position("home")

    def update_threshold(self, value):
        conf = value / 100.0
        self.ui.threshold_value.setText(f"{conf:.2f}")
        if self.detector:
            self.detector.conf_thres = conf

    def update_servo(self, value):
        self.ui.servo_value.setText(f"{value}°")
        self.robot_arm.set_joint_angle(0, value - 90)

    def toggle_conveyor(self):
        if self.is_conveyor_on:
            self.conveyor.stop()
            self.ui.conveyor_btn.setText("▶️ 啟動輸送帶")
            self.update_status_label(self.ui.conveyor_status, "輸送帶狀態：🟢 停止", "green")
        else:
            self.conveyor.start_forward()
            self.ui.conveyor_btn.setText("⏸️ 停止輸送帶")
            self.update_status_label(self.ui.conveyor_status, "輸送帶狀態：🟡 移動中...", "orange")
        self.is_conveyor_on = not self.is_conveyor_on

    def reset_system(self):
        self.conveyor.stop()
        self.robot_arm.move_to_named_position("home")
        self.update_status_label(self.ui.system_status, "系統狀態：🟢 就緒", "green")

    def closeEvent(self, event):
        self.stop_auto_detection()
        self.worker.wait()
        self.conveyor.disconnect()
        self.robot_arm.cleanup()
        event.accept()

    def update_status_label(self, label, text, color):
        label.setText(text)
        label.setStyleSheet(f"color: {color}; font-weight: bold;")

    def update_image_display(self, pixmap):
        scaled_pixmap = pixmap.scaled(self.ui.image_display.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.ui.image_display.setPixmap(scaled_pixmap)

    def add_log_entry(self, log_data):
        row_pos = self.ui.log_table.rowCount()
        self.ui.log_table.insertRow(row_pos)
        for col, data in enumerate(log_data):
            self.ui.log_table.setItem(row_pos, col, QTableWidgetItem(str(data)))
        self.ui.log_table.scrollToBottom()

    def update_stats(self, stats):
        self.ui.total_label.setText(f"總檢測數：{stats['total']}")
        self.ui.pass_label.setText(f"合格數：{stats['pass']}")
        self.ui.defect_label.setText(f"缺陷數：{stats['defect']}")
        self.ui.pass_rate_label.setText(f"合格率：{stats['rate']:.2f}%")


if __name__ == '__main__':
    for folder in ["live_captured_images", "processed_images", "weights"]:
        if not os.path.exists(folder):
            os.makedirs(folder)
    if not os.path.exists(YOLO_WEIGHTS_PATH):
         print(f"警告：找不到模型 '{YOLO_WEIGHTS_PATH}'。請將權重檔案放入 'weights' 資料夾。")

    app = QApplication(sys.argv)
    window = PCBAMainWindow()
    window.show()
    sys.exit(app.exec_())
