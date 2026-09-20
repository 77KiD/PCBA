"""
檢測引擎模組 - 三分類版本
負責PCB缺陷檢測邏輯和演算法 (鼠咬、斷路、雜銅)
根據檢測到的缺陷種類數量進行分類：
- 單一缺陷：檢測到1種缺陷
- 兩種缺陷：檢測到2種缺陷
- 多種缺陷：檢測到3種及以上缺陷
"""

import time
import random
import numpy as np
import cv2
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot

class DetectionEngine:
    """檢測引擎類 - 專門針對鼠咬/斷路/雜銅檢測 (三分類版本)"""
    
    def __init__(self):
        self.threshold = 0.5  # 預設閾值
        # 更新缺陷類型為鼠咬、斷路、雜銅
        self.defect_types = ["鼠咬", "斷路", "雜銅"]
        
        # 缺陷類型的英文對照
        self.defect_mapping = {
            'mouse_bite': '鼠咬',
            'mousebite': '鼠咬',
            'mouse bite': '鼠咬',
            'open_circuit': '斷路',
            'open circuit': '斷路',
            'open': '斷路',
            'break': '斷路',
            'copper': '雜銅',
            'copper_contamination': '雜銅',
            'contamination': '雜銅'
        }
        
    def detect_pcba(self, frame):
        """
        PCB缺陷檢測邏輯 - 返回缺陷種類數量
        
        Args:
            frame: OpenCV影像幀
            
        Returns:
            tuple: (檢測結果, 缺陷列表, 信心分數)
                  檢測結果: "合格" / "單一缺陷" / "兩種缺陷" / "多種缺陷"
        """
        if frame is None:
            return "錯誤", [], 0.0
            
        # 模擬檢測過程
        time.sleep(0.1)
        
        # 基於閾值和隨機因素決定檢測結果
        detection_score = random.random()
        
        if detection_score > self.threshold:
            return "合格", [], detection_score
        else:
            # 隨機決定檢測到的缺陷種類數量 (1-3種)
            num_defect_types = random.randint(1, 3)
            
            # 隨機選擇缺陷類型（不重複）
            detected_defects = random.sample(self.defect_types, num_defect_types)
            
            # 根據缺陷種類數量返回分類結果
            if num_defect_types == 1:
                result = "單一缺陷"
            elif num_defect_types == 2:
                result = "兩種缺陷"
            else:  # 3種及以上
                result = "多種缺陷"
            
            return result, detected_defects, detection_score
    
    def analyze_detection_results(self, detections):
        """
        分析檢測結果，統計缺陷種類數量
        
        Args:
            detections: 檢測結果列表 (來自 YOLOv12)
            
        Returns:
            tuple: (分類結果, 缺陷列表, 平均信心度)
        """
        if not detections:
            return "合格", [], 0.0
        
        # 統計檢測到的缺陷種類
        detected_defect_types = set()
        total_confidence = 0
        
        defect_classes = {
            '鼠咬': ['鼠咬', 'mouse_bite', 'mousebite', 'mouse bite'],
            '斷路': ['斷路', 'open_circuit', 'open', 'break'],
            '雜銅': ['雜銅', 'copper', 'copper_contamination', 'contamination']
        }
        
        for detection in detections:
            class_name_lower = detection.class_name.lower()
            
            # 判斷屬於哪種缺陷類型
            for defect_type, keywords in defect_classes.items():
                if any(keyword in class_name_lower for keyword in keywords):
                    detected_defect_types.add(defect_type)
                    total_confidence += detection.confidence
                    break
        
        # 如果沒有檢測到已知的缺陷類型，視為合格
        if len(detected_defect_types) == 0:
            avg_confidence = max([d.confidence for d in detections]) if detections else 0.0
            return "合格", [], avg_confidence
        
        # 計算平均信心度
        avg_confidence = total_confidence / len(detections) if detections else 0.0
        
        # 根據缺陷種類數量分類
        defect_list = list(detected_defect_types)
        num_types = len(defect_list)
        
        if num_types == 1:
            result = "單一缺陷"
            print(f"🔍 檢測到單一缺陷: {defect_list[0]} (信心度: {avg_confidence:.2f})")
        elif num_types == 2:
            result = "兩種缺陷"
            print(f"🔍 檢測到兩種缺陷: {', '.join(defect_list)} (信心度: {avg_confidence:.2f})")
        else:  # 3種及以上
            result = "多種缺陷"
            print(f"🔍 檢測到多種缺陷: {', '.join(defect_list)} (信心度: {avg_confidence:.2f})")
        
        return result, defect_list, avg_confidence
    
    def map_defect_name(self, english_name):
        """
        將英文缺陷名稱映射為中文
        
        Args:
            english_name: 英文缺陷名稱
            
        Returns:
            str: 中文缺陷名稱
        """
        if not english_name:
            return None
            
        english_name_lower = english_name.lower()
        
        # 檢查映射表
        for eng_key, chi_name in self.defect_mapping.items():
            if eng_key in english_name_lower:
                return chi_name
        
        # 已經是中文，直接返回
        if english_name in self.defect_types:
            return english_name
            
        # 未知類型
        return None
    
    def analyze_defect_severity(self, defect_list):
        """
        分析缺陷嚴重程度（基於種類數量）
        
        Args:
            defect_list: 缺陷類型列表
            
        Returns:
            int: 嚴重程度 (1-3)
        """
        num_types = len(defect_list)
        
        if num_types == 1:
            return 1  # 單一缺陷 - 輕微
        elif num_types == 2:
            return 2  # 兩種缺陷 - 中等
        else:
            return 3  # 多種缺陷 - 嚴重
    
    def get_classification_result(self, num_defect_types):
        """
        根據缺陷種類數量獲取分類結果
        
        Args:
            num_defect_types: 缺陷種類數量
            
        Returns:
            str: 分類結果
        """
        if num_defect_types == 0:
            return "合格"
        elif num_defect_types == 1:
            return "單一缺陷"
        elif num_defect_types == 2:
            return "兩種缺陷"
        else:
            return "多種缺陷"
    
    def set_threshold(self, threshold):
        """設置檢測閾值"""
        self.threshold = max(0.0, min(1.0, threshold))
        print(f"🔧 檢測閾值已更新: {self.threshold:.2f}")
    
    def get_threshold(self):
        """獲取當前閾值"""
        return self.threshold
    
    def analyze_image(self, frame):
        """
        分析影像品質和特徵
        
        Args:
            frame: OpenCV影像幀
            
        Returns:
            dict: 分析結果
        """
        if frame is None:
            return {"error": "無效影像"}
        
        # 計算影像基本特徵
        height, width = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        
        # 計算統計特徵
        mean_brightness = np.mean(gray)
        std_brightness = np.std(gray)
        
        # 計算邊緣密度（作為複雜度指標）
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / (width * height)
        
        return {
            "width": width,
            "height": height,
            "mean_brightness": float(mean_brightness),
            "std_brightness": float(std_brightness),
            "edge_density": float(edge_density),
            "quality_score": self._calculate_quality_score(mean_brightness, std_brightness, edge_density)
        }
    
    def _calculate_quality_score(self, brightness, std, edge_density):
        """計算影像品質分數"""
        # 簡化的品質評估
        brightness_score = 1.0 - abs(brightness - 127.5) / 127.5
        contrast_score = min(std / 50.0, 1.0)
        detail_score = min(edge_density * 10, 1.0)
        
        return (brightness_score + contrast_score + detail_score) / 3.0


class DetectionThread(QThread):
    """檢測線程 - 三分類版本"""
    # 修改信號：增加缺陷列表參數
    detection_result = pyqtSignal(str, list, float)  # result, defect_list, confidence
    sensor_triggered = pyqtSignal()
    
    def __init__(self, hardware_controller, system_ref):
        super().__init__()
        self.hardware = hardware_controller
        self.system_ref = system_ref
        self.detection_engine = DetectionEngine()
        self.running = False
        self.processing = False
        
    def run(self):
        """運行檢測邏輯"""
        self.running = True
        last_sensor_state = False
        
        while self.running:
            try:
                # 檢查系統是否啟動檢測
                if not hasattr(self.system_ref, 'is_running') or not self.system_ref.is_running:
                    time.sleep(0.1)
                    continue
                
                # 檢查輸送帶是否運行
                if not hasattr(self.system_ref, 'conveyor_running') or not self.system_ref.conveyor_running:
                    time.sleep(0.1)
                    continue
                
                # 讀取感測器狀態
                current_sensor_state = self.hardware.read_sensor()
                
                # 檢測到物體
                if current_sensor_state and not last_sensor_state and not self.processing:
                    self.processing = True
                    self.sensor_triggered.emit()
                    
                    # 獲取相機畫面進行檢測
                    frame = self.hardware.get_camera_frame()
                    if frame is not None:
                        result, defect_list, confidence = self.detection_engine.detect_pcba(frame)
                        self.detection_result.emit(result, defect_list, confidence)
                        
                        # 不在這裡控制分類，交給 IR2 處理
                    
                    time.sleep(1.0)
                    self.processing = False
                
                last_sensor_state = current_sensor_state
                time.sleep(0.05)
                
            except Exception as e:
                print(f"檢測線程錯誤: {e}")
                time.sleep(0.1)
    
    def set_threshold(self, threshold):
        """設置檢測閾值"""
        self.detection_engine.set_threshold(threshold)
    
    def get_threshold(self):
        """獲取檢測閾值"""
        return self.detection_engine.get_threshold()
    
    def stop(self):
        """停止檢測"""
        self.running = False
        self.quit()
        self.wait(3000)


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
            try:
                frame = self.hardware.get_camera_frame()
                if frame is not None:
                    self.frame_ready.emit(frame)
                time.sleep(0.033)  # ~30 FPS
            except Exception as e:
                print(f"相機線程錯誤: {e}")
                time.sleep(0.1)
    
    def stop(self):
        """停止線程"""
        self.running = False
        self.quit()
        self.wait(3000)


# 測試函數
def test_detection_engine():
    """測試檢測引擎 - 三分類版本"""
    print("🧪 測試PCB缺陷檢測引擎 (三分類版本)...")
    
    engine = DetectionEngine()
    
    # 測試檢測功能
    print("\n1. 測試檢測功能:")
    test_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    for i in range(5):
        result, defect_list, confidence = engine.detect_pcba(test_image)
        print(f"   測試 {i+1}: {result}")
        if defect_list:
            print(f"      缺陷類型: {', '.join(defect_list)}")
        print(f"      信心度: {confidence:.2f}")
    
    # 測試分類邏輯
    print("\n2. 測試分類邏輯:")
    test_cases = [
        (0, "合格"),
        (1, "單一缺陷"),
        (2, "兩種缺陷"),
        (3, "多種缺陷")
    ]
    
    for num, expected in test_cases:
        result = engine.get_classification_result(num)
        print(f"   {num}種缺陷 → {result} (預期: {expected})")
    
    print("\n✅ 檢測引擎測試完成！")


if __name__ == '__main__':
    test_detection_engine()