"""
Hardware Controller
移除 Arduino 連接以避免與 ArduinoSerialThread 衝突
只保留相機和其他必要的硬體控制
"""


import cv2
import time

GPIO_AVAILABLE = False


class HardwareController:
    """硬體控制器 - 專注於相機管理"""
    
    def __init__(self):
        self.camera = None
        self.camera_index = 0
        
    def init_hardware(self):
        """初始化硬體 - 只初始化相機"""
        print("🔧 初始化硬體控制器...")
        self.init_camera()
    
    def init_camera(self):
        """初始化相機"""
        try:
            print(f"🔄 嘗試初始化相機 index={self.camera_index}")
            self.camera = cv2.VideoCapture(self.camera_index)
            
            if self.camera.isOpened():
                # 設定相機參數
                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                self.camera.set(cv2.CAP_PROP_FPS, 30)
                
                # 測試讀取
                ret, frame = self.camera.read()
                if ret:
                    print("✅ 相機初始化成功")
                    return True
                else:
                    print("⚠️ 相機無法讀取畫面")
                    self.camera.release()
                    self.camera = None
            else:
                print("❌ 相機無法開啟")
                self.camera = None
                
        except Exception as e:
            print(f"❌ 相機初始化失敗: {e}")
            self.camera = None
            
        return False
    
    def get_camera_frame(self):
        """獲取相機畫面"""
        if self.camera is None or not self.camera.isOpened():
            # 嘗試重新初始化
            self.init_camera()
            
        if self.camera and self.camera.isOpened():
            ret, frame = self.camera.read()
            if ret:
                return frame
        
        return None
    
    def get_hardware_status(self):
        """獲取硬體狀態"""
        status = {
            'camera': self.camera is not None and self.camera.isOpened(),
            'camera_resolution': '640x480' if self.camera and self.camera.isOpened() else 'N/A'
        }
        return status
    
    def set_conveyor_speed(self, speed):
        """設置輸送帶速度 (空實現，實際控制在 Arduino)"""
        # 這個功能由 Arduino 的 PWM 控制
        # 如果需要可以通過 ArduinoSerialThread 發送命令
        pass
    
    def cleanup(self):
        """清理資源"""
        if self.camera is not None:
            self.camera.release()
            self.camera = None
            print("✅ 相機已釋放")
    
    def __del__(self):
        """析構函數"""
        self.cleanup()


# 測試代碼
if __name__ == "__main__":
    print("="*70)
    print("  Hardware Controller 測試")
    print("="*70)
    
    hw = HardwareController()
    hw.init_hardware()
    
    if hw.camera:
        print("\n測試相機擷取...")
        for i in range(5):
            frame = hw.get_camera_frame()
            if frame is not None:
                print(f"✅ 第 {i+1} 幀: {frame.shape}")
            else:
                print(f"❌ 第 {i+1} 幀: 失敗")
            time.sleep(0.5)
        
        # 儲存測試圖片
        frame = hw.get_camera_frame()
        if frame is not None:
            cv2.imwrite("test_frame.jpg", frame)
            print("\n✅ 已儲存測試圖片: test_frame.jpg")
    
    hw.cleanup()
    print("\n✅ 測試完成")