"""
影像處理和YOLOv12推論模組
專門針對PCB缺陷檢測: 鼠咬、斷路、雜銅
"""

import cv2
import numpy as np
import time
import os
from typing import Tuple, List, Dict, Optional
from dataclasses import dataclass

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
    print("✅ YOLOv12/ultralytics 可用")
except ImportError:
    YOLO_AVAILABLE = False
    print("⚠️ YOLOv12/ultralytics 未安裝，將使用模擬推論")

@dataclass
class DetectionResult:
    """檢測結果數據類"""
    class_id: int
    class_name: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2
    center: Tuple[int, int]

@dataclass
class ProcessingConfig:
    """影像處理配置"""
    # 邊緣檢測參數
    canny_low: int = 50
    canny_high: int = 150
    canny_aperture: int = 3
    
    # 高斯濾波參數
    gaussian_kernel: int = 5
    gaussian_sigma: float = 1.0
    
    # 對比度增強參數
    contrast_alpha: float = 1.5
    brightness_beta: int = 10

    # 顯示開關：是否把邊緣圖疊在 YOLO 圖上
    show_edges: bool = False   # 預設關閉
    
    # YOLO推論參數 (針對PCB缺陷檢測優化)
    yolo_confidence: float = 0.5  # 信心閾值
    yolo_iou: float = 0.4        # NMS IoU閾值
    yolo_max_detections: int = 20 # 最大檢測數量 
    
    # 顯示參數
    show_edges: bool = True
    show_enhanced: bool = True
    show_detections: bool = True

class ImageProcessor:
    """影像處理器類 - 專門針對鼠咬/斷路/雜銅檢測"""
    
    def __init__(self, model_path: str = "best.pt", class_names: Optional[Dict[int, str]] = None):
        """
        初始化影像處理器
        
        Args:
            model_path: YOLO模型路徑
            class_names: 自定義類別名稱字典
        """
        self.config = ProcessingConfig()
        self.yolo_model = None
        self.model_path = model_path
        self.processing_stats = {
            'frame_count': 0,
            'processing_time': 0.0,
            'inference_time': 0.0
        }
        
        # PCB缺陷類別定義
        if class_names:
            self.pcb_classes = class_names
            print(f"📋 使用自定義類別: {list(class_names.values())}")
        else:
            # 預設類別 (根據的訓練模型調整)
            self.pcb_classes = {
                0: '鼠咬',         # Mouse Bite
                1: '斷路',         # Open Circuit
                2: '雜銅',         # Copper Contamination
                3: 'mouse_bite',  # 英文別名
                4: 'open_circuit',
                5: 'copper',
                6: 'pcb',         # 正常PCB
                7: 'normal'       # 正常區域
            }
        
        self.init_yolo_model()
    
    def init_yolo_model(self):
        """初始化YOLO模型"""
        if not YOLO_AVAILABLE:
            print("⚠️ YOLO模組不可用，將使用模擬推論")
            return
        
        if not os.path.exists(self.model_path):
            print(f"❌ 模型檔案不存在: {self.model_path}")
            print("💡 請確認模型路徑正確，或將訓練好的 best.pt 放在正確位置")
            return
            
        try:
            print(f"🔄 載入YOLO模型: {self.model_path}")
            
            # 載入模型
            self.yolo_model = YOLO(self.model_path)
            
            # 獲取模型的類別名稱
            if hasattr(self.yolo_model, 'names') and self.yolo_model.names:
                model_classes = self.yolo_model.names
                print(f"📋 模型內建類別: {model_classes}")
                
                # 更新類別名稱 (相容 dict / list 兩種形式)
                self.pcb_classes = {}

                if isinstance(model_classes, dict):
                    # model.names = {0: 'mb', 1: 'op', 2: 'sc'}
                    for i, name in model_classes.items():
                        self.pcb_classes[int(i)] = str(name)
                else:
                    # model.names = ['mb', 'op', 'sc']
                    for i, name in enumerate(model_classes):
                        self.pcb_classes[int(i)] = str(name)

                # 映射英文/縮寫到中文
                self._map_class_names()
            
            # 暖機運行
            print("🔥 模型暖機中...")
            dummy_image = np.zeros((640, 640, 3), dtype=np.uint8)
            _ = self.yolo_model.predict(dummy_image, verbose=False)
            
            print("✅ YOLO模型載入成功！")
            print(f"📊 模型資訊:")
            print(f"   - 類別數量: {len(self.pcb_classes)}")
            print(f"   - 檢測類別: {list(set(self.pcb_classes.values()))}")
            
        except Exception as e:
            print(f"❌ YOLO模型載入失敗: {e}")
            print("💡 建議檢查:")
            print("   1. 模型檔案是否完整")
            print("   2. ultralytics 版本是否正確 (pip install -U ultralytics)")
            print("   3. PyTorch 是否已安裝")
            self.yolo_model = None

    
    def _map_class_names(self):
        """把模型裡的英文/縮寫類別名稱，統一映射成中文名稱"""
        name_mapping = {
            # 鼠咬
            'mouse_bite': '鼠咬',
            'mousebite': '鼠咬',
            'mouse bite': '鼠咬',
            'bite': '鼠咬',
            'mb': '鼠咬',      

            # 斷路
            'open_circuit': '斷路',
            'open circuit': '斷路',
            'open': '斷路',
            'break': '斷路',
            'op': '斷路',      

            # 雜銅
            'short_circuit': '雜銅',
            'short circuit': '雜銅',
            'short': '雜銅',
            'copper': '雜銅',
            'copper_contamination': '雜銅',
            'contamination': '雜銅',
            'sc': '雜銅',      
        }

        for class_id, class_name in self.pcb_classes.items():
            # 一律轉字串再 lower
            class_name_lower = str(class_name).lower()   
            if class_name_lower in name_mapping:
                self.pcb_classes[class_id] = name_mapping[class_name_lower]

    
    def apply_edge_detection(self, image: np.ndarray) -> np.ndarray:
        """邊緣檢測處理 - 有助於檢測鼠咬和斷路"""
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # 高斯模糊降噪
        blurred = cv2.GaussianBlur(
            gray, 
            (self.config.gaussian_kernel, self.config.gaussian_kernel),
            self.config.gaussian_sigma
        )
        
        # Canny邊緣檢測
        edges = cv2.Canny(
            blurred,
            self.config.canny_low,
            self.config.canny_high,
            apertureSize=self.config.canny_aperture
        )
        
        # 轉換為三通道
        edges_colored = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
        return edges_colored
    
    def apply_enhancement(self, image: np.ndarray) -> np.ndarray:
        """影像增強處理 - 提升缺陷可見度"""
        # 對比度和亮度調整
        enhanced = cv2.convertScaleAbs(
            image, 
            alpha=self.config.contrast_alpha, 
            beta=self.config.brightness_beta
        )
        
        # 銳化濾波器
        sharpening_kernel = np.array([
            [-1, -1, -1],
            [-1,  9, -1], 
            [-1, -1, -1]
        ])
        
        # 應用銳化
        sharpened = cv2.filter2D(enhanced, -1, sharpening_kernel)
        
        # 高斯濾波平滑
        smoothed = cv2.GaussianBlur(
            sharpened,
            (self.config.gaussian_kernel, self.config.gaussian_kernel),
            self.config.gaussian_sigma
        )
        
        return smoothed
    
    def run_yolo_inference(self, image: np.ndarray) -> Tuple[np.ndarray, List[DetectionResult]]:
        """
        運行YOLOv12推論
        
        Args:
            image: 輸入影像
            
        Returns:
            (帶檢測框的影像, 檢測結果列表)
        """
        start_time = time.time()
        
        if not self.yolo_model:
            print("⚠️ 模型未載入，使用模擬推論")
            return self._simulate_yolo_inference(image)
        
        try:
            # YOLOv12推論
            results = self.yolo_model.predict(
                image,
                conf=self.config.yolo_confidence,
                iou=self.config.yolo_iou,
                max_det=self.config.yolo_max_detections,
                verbose=False
            )
            
            detections = []
            annotated_image = image.copy()
            
            if results and len(results) > 0:
                result = results[0]
                
                if result.boxes is not None and len(result.boxes) > 0:
                    boxes = result.boxes.cpu().numpy()
                    
                    for box in boxes:
                        # 提取檢測資訊
                        x1, y1, x2, y2 = box.xyxy[0].astype(int)
                        confidence = float(box.conf[0])
                        class_id = int(box.cls[0])
                        
                        # 獲取類別名稱
                        class_name = self.pcb_classes.get(class_id, f"class_{class_id}")
                        
                        # 計算中心點
                        center_x = int((x1 + x2) / 2)
                        center_y = int((y1 + y2) / 2)
                        
                        # 創建檢測結果
                        detection = DetectionResult(
                            class_id=class_id,
                            class_name=class_name,
                            confidence=confidence,
                            bbox=(x1, y1, x2, y2),
                            center=(center_x, center_y)
                        )
                        detections.append(detection)
                        
                        # 繪製檢測框
                        if self.config.show_detections:
                            self._draw_detection(annotated_image, detection)
                    
                    # 按信心度排序
                    detections.sort(key=lambda x: x.confidence, reverse=True)
                    
                    print(f"🎯 檢測到 {len(detections)} 個物件:")
                    for det in detections:
                        print(f"   - {det.class_name}: {det.confidence:.2f}")
                else:
                    print("ℹ️ 未檢測到任何缺陷")
            
            self.processing_stats['inference_time'] = time.time() - start_time
            
            return annotated_image, detections
            
        except Exception as e:
            print(f"❌ YOLO推論錯誤: {e}")
            import traceback
            traceback.print_exc()
            return self._simulate_yolo_inference(image)
    
    def _simulate_yolo_inference(self, image: np.ndarray) -> Tuple[np.ndarray, List[DetectionResult]]:
        """模擬YOLOv12推論 (測試用)"""
        annotated_image = image.copy()
        detections = []
        
        h, w = image.shape[:2]
        
        # 隨機模擬缺陷檢測
        defect_types = ['鼠咬', '斷路', '雜銅']
        
        # 30% 機率檢測到缺陷
        if np.random.random() > 0.7:
            num_defects = np.random.randint(1, 3)
            
            for i in range(num_defects):
                x1 = np.random.randint(0, w//2)
                y1 = np.random.randint(0, h//2)
                x2 = x1 + np.random.randint(50, 150)
                y2 = y1 + np.random.randint(30, 100)
                
                x2 = min(x2, w-1)
                y2 = min(y2, h-1)
                
                defect_type = defect_types[i % len(defect_types)]
                
                detection = DetectionResult(
                    class_id=i,
                    class_name=defect_type,
                    confidence=0.6 + np.random.random() * 0.3,
                    bbox=(x1, y1, x2, y2),
                    center=((x1+x2)//2, (y1+y2)//2)
                )
                detections.append(detection)
                self._draw_detection(annotated_image, detection)
        
        return annotated_image, detections
    
    def _draw_detection(self, image: np.ndarray, detection: DetectionResult):
        """在影像上繪製檢測結果（使用英文標籤避免顯示成問號）"""
        x1, y1, x2, y2 = detection.bbox

        # 根據缺陷類型選擇顏色
        color_map = {
            '鼠咬': (0, 0, 255),        # 紅色
            'mouse_bite': (0, 0, 255),
            'mousebite': (0, 0, 255),
            '斷路': (255, 0, 0),        # 藍色
            'open_circuit': (255, 0, 0),
            'open': (255, 0, 0),
            '雜銅': (0, 165, 255),      # 橙色
            'copper': (0, 165, 255),
            'contamination': (0, 165, 255),
            'pcb': (0, 255, 0),         # 綠色
            'normal': (0, 255, 0)
        }

        # 尋找匹配的顏色
        color = (128, 128, 128)  # 預設灰色
        class_name_lower = detection.class_name.lower()
        for key, col in color_map.items():
            if key.lower() in class_name_lower:
                color = col
                break

        # 繪製檢測框
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 3)

        # 這裡改成英文標籤，避免中文變成 
        display_name_map = {
            '鼠咬': 'MB',
            '斷路': 'OP',
            '雜銅': 'SC',
        }

        raw_name = detection.class_name
        display_name = display_name_map.get(raw_name, raw_name)

        # 確保只包含 ASCII 字元（OpenCV 內建字型只保證這個）
        safe_name = ''.join(ch if ord(ch) < 128 else '_' for ch in display_name)

        label = f"{safe_name} {detection.confidence:.2f}"

        # 計算標籤尺寸
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6
        thickness = 2
        label_size = cv2.getTextSize(label, font, font_scale, thickness)[0]

        # 標籤背景
        label_y = max(y1 - 10, label_size[1] + 10)
        cv2.rectangle(
            image,
            (x1, label_y - label_size[1] - 10),
            (x1 + label_size[0] + 10, label_y + 5),
            color,
            -1
        )

        # 標籤文字（英文）
        cv2.putText(
            image,
            label,
            (x1 + 5, label_y),
            font,
            font_scale,
            (255, 255, 255),
            thickness
        )

        # 繪製中心點
        center_x, center_y = detection.center
        cv2.circle(image, (center_x, center_y), 5, color, -1)

    
    def process_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, np.ndarray, List[DetectionResult]]:
        """
        處理單幀影像
        
        Args:
            frame: 原始影像幀
            
        Returns:
            (邊緣檢測影像, YOLO推論影像, 檢測結果)
        """
        start_time = time.time()
        
        if frame is None:
            empty = np.zeros((480, 640, 3), dtype=np.uint8)
            return empty, empty, []
        
        # 1. 邊緣檢測
        # edges_image = self.apply_edge_detection(frame)
        edges_image = None  # 👉 先關掉邊緣圖，專心看原圖 + 框

        # 2. 不再做增強（
        # enhanced_frame = self.apply_enhancement(frame)

        # 3. YOLOv12 推論直接用「原始畫面」來辨識
        yolo_image, detections = self.run_yolo_inference(frame)

        # 4. 合成結果
        processed_image = self._combine_processing_results(edges_image, yolo_image)

        
        # 更新統計
        self.processing_stats['frame_count'] += 1
        self.processing_stats['processing_time'] = time.time() - start_time
        
        return edges_image, processed_image, detections
    
    def _combine_processing_results(self, edges_image, yolo_image):
        """
        將邊緣圖和 YOLO 結果圖疊加。
        - 沒有 YOLO → 回傳 edges_image
        - 沒有 edges 或關閉邊緣顯示 → 回傳 yolo_image
        """
        if yolo_image is None and edges_image is None:
            return None
        if yolo_image is None:
            return edges_image
        if edges_image is None or not self.config.show_edges:
            return yolo_image

        h, w = yolo_image.shape[:2]
        edges_resized = cv2.resize(edges_image, (w, h))

        # 灰階 BGR
        if len(edges_resized.shape) == 2:
            edges_color = cv2.cvtColor(edges_resized, cv2.COLOR_GRAY2BGR)
        else:
            edges_color = edges_resized

        return cv2.addWeighted(yolo_image, 0.8, edges_color, 0.2, 0)



    
    def get_processing_stats(self) -> Dict:
        """獲取處理統計資訊"""
        fps = 0
        if self.processing_stats['processing_time'] > 0:
            fps = 1.0 / self.processing_stats['processing_time']
            
        return {
            'frame_count': self.processing_stats['frame_count'],
            'processing_time': self.processing_stats['processing_time'],
            'inference_time': self.processing_stats['inference_time'],
            'fps': fps,
            'yolo_available': self.yolo_model is not None,
            'model_path': self.model_path,
            'num_classes': len(self.pcb_classes)
        }
    
    def update_config(self, **kwargs):
        """更新處理配置"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                print(f"🔧 更新配置 {key} = {value}")
    
    def reset_stats(self):
        """重設統計資訊"""
        self.processing_stats = {
            'frame_count': 0,
            'processing_time': 0.0,
            'inference_time': 0.0
        }
    
    def reload_model(self, new_model_path: str):
        """
        重新載入模型
        
        Args:
            new_model_path: 新模型路徑
        """
        print(f"🔄 重新載入模型: {new_model_path}")
        self.model_path = new_model_path
        self.yolo_model = None
        self.init_yolo_model()


    # 測試函數
    def test_image_processor():
        """測試影像處理器"""
        print("🧪 測試影像處理器 - 鼠咬/斷路/雜銅檢測...")
        
        # 自定義類別
        custom_classes = {
            0: '鼠咬',
            1: '斷路',
            2: '雜銅'
        }
        
        processor = ImageProcessor(
            model_path="best.pt",
            class_names=custom_classes
        )
        
        # 創建測試影像
        test_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        
        # 處理影像
        edges, processed, detections = processor.process_frame(test_image)
        
        print(f"✅ 邊緣檢測影像尺寸: {edges.shape}")
        print(f"✅ 處理後影像尺寸: {processed.shape}")
        print(f"✅ 檢測到 {len(detections)} 個缺陷")
        
        for i, det in enumerate(detections):
            print(f"   {i+1}. {det.class_name} (信心度: {det.confidence:.2f})")
        
        # 顯示統計
        stats = processor.get_processing_stats()
        print(f"\n📊 處理統計:")
        for key, value in stats.items():
            print(f"   - {key}: {value}")


if __name__ == '__main__':
    test_image_processor()