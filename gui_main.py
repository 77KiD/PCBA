# gui_main.py
import sys
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtGui import QImage, QPixmap
from ui import PCBAUIInterface
from yolo_inference import YOLOv12Detector
from camera_capture import capture_image
from conveyor_control import ConveyorControl
from robot_arm_control import RobotArmControl
import cv2

class PCBAMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # 初始化 UI
        self.ui = PCBAUIInterface(self)

        # 初始化模組
        self.init_modules()

        # 綁定按鈕事件
        self.ui.connect_signals(self)

    def init_modules(self):
        # 路徑與參數
        yolo_weights = r"C:\Users\s1593\Downloads\PCBA-main\PCBA-main\YOLO12\runs\detect\pcb_yolo12x_retry\weights\best.pt"
        self.detector = YOLOv12Detector(weights_path=yolo_weights, device='cpu')  # 或 'cuda'
        self.conveyor = ConveyorControl(control_type="custom")
        self.robot_arm = RobotArmControl(
            joint_pins=[17, 18, 27, 22, 23, 24],
            gripper_pin=25,
            pwm_lib_type="custom"
        )

    def start_auto_detection(self):
        print("開始自動檢測流程...")

        image_path = capture_image(output_dir="live_captured_images", filename_prefix="gui_capture")
        if not image_path:
            print("❌ 影像擷取失敗")
            return

        print(f"✅ 影像擷取成功: {image_path}")

        # 顯示圖片
        img = cv2.imread(image_path)
        if img is not None:
            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_img.shape
            qt_img = QImage(rgb_img.data, w, h, ch * w, QImage.Format_RGB888)
            self.ui.image_display.setPixmap(QPixmap.fromImage(qt_img).scaled(
                self.ui.image_display.size(), aspectRatioMode=1))

        # 推論
        detections = self.detector.detect(image_path)
        print(f"🧠 推論結果: {detections}")

    def stop_auto_detection(self):
        print("🛑 停止自動檢測（尚未實作）")

    def update_threshold(self, value):
        conf = value / 100.0
        self.ui.threshold_value.setText(f"{conf:.2f}")
        self.detector.conf_thres = conf
        print(f"🎚️ 更新門檻值為: {conf:.2f}")

    def update_servo(self, value):
        self.ui.servo_value.setText(f"{value}°")
        print(f"🎚️ 模擬調整伺服角度為: {value}°")

    def update_conveyor_speed(self, value):
        self.ui.speed_value.setText(f"{value}%")
        print(f"🎚️ 模擬調整輸送帶速度為: {value}%")

    def toggle_conveyor(self):
        print("🔄 模擬啟動/停止輸送帶")

    def reset_system(self):
        print("🔃 模擬系統重設")

    def toggle_relay(self):
        print("🔌 模擬繼電器切換")

    def export_report(self):
        print("📤 模擬匯出報告")

    def clear_records(self):
        print("🗑️ 模擬清除記錄")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = PCBAMainWindow()
    window.show()
    sys.exit(app.exec_())
