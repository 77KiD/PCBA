import torch
from ultralytics import YOLO
import cv2
import numpy as np
import os


class YOLOv12Detector:
    def __init__(self, weights_path, device='cpu', conf_thres=0.25, iou_thres=0.45, img_size=640):
        """
        使用 Ultralytics YOLOv12 載入模型
        
        Args:
            weights_path (str): 模型權重檔案路徑
            device (str): 使用的裝置 ('cpu' 或 'cuda')
            conf_thres (float): 信心度閾值
            iou_thres (float): IoU 閾值
            img_size (int): 輸入圖片尺寸
        """
        self.device = device
        self.conf_thres = conf_thres
        self.iou_thres = iou_thres
        self.img_size = img_size
        self.model = None
        self.names = {}
        
        # 檢查權重檔案是否存在
        if not os.path.exists(weights_path):
            print(f"錯誤：模型權重檔案 '{weights_path}' 不存在。")
            return
            
        try:
            print(f"正在從 {weights_path} 載入模型...")
            
            # 使用 Ultralytics YOLO 載入模型
            self.model = YOLO(weights_path)
            
            # 設定裝置
            if device == 'cuda' and torch.cuda.is_available():
                print("使用 GPU (CUDA) 進行推論")
            else:
                print("使用 CPU 進行推論")
                self.device = 'cpu'
            
            # 獲取類別名稱
            self.names = self.model.names if hasattr(self.model, 'names') else {}
            
            print(f"模型載入成功！")
            print(f"類別數量: {len(self.names)}")
            if self.names:
                print(f"類別名稱: {list(self.names.values())}")
                
        except Exception as e:
            print(f"錯誤：載入模型失敗。{e}")
            self.model = None

    def detect(self, image_path_or_frame):
        """
        對圖片進行偵測，回傳標籤、信心度與座標。
        
        Args:
            image_path_or_frame: 圖片路徑或 OpenCV frame
            
        Returns:
            list: 偵測結果列表，每個元素包含 'label', 'confidence', 'bbox'
        """
        if self.model is None:
            print("錯誤：模型尚未載入。")
            return []

        # 讀取圖片
        if isinstance(image_path_or_frame, str):
            if not os.path.exists(image_path_or_frame):
                print(f"錯誤：圖片檔案 '{image_path_or_frame}' 不存在。")
                return []
            img = cv2.imread(image_path_or_frame)
            if img is None:
                print(f"錯誤：無法讀取圖片 {image_path_or_frame}")
                return []
        elif isinstance(image_path_or_frame, np.ndarray):
            img = image_path_or_frame
        else:
            print("錯誤：輸入格式錯誤，請提供圖片路徑或 OpenCV frame。")
            return []

        try:
            # 使用 Ultralytics YOLO 進行預測
            results = self.model.predict(
                source=img,
                conf=self.conf_thres,
                iou=self.iou_thres,
                device=0 if self.device == 'cuda' and torch.cuda.is_available() else 'cpu',
                verbose=False,
                imgsz=self.img_size
            )

            detections = []
            
            # 解析結果
            for result in results:
                if result.boxes is not None:
                    boxes = result.boxes
                    for box in boxes:
                        # 獲取類別 ID 和標籤
                        cls_id = int(box.cls[0])
                        label = self.names.get(cls_id, f'class_{cls_id}')
                        
                        # 獲取信心度
                        conf = float(box.conf[0])
                        
                        # 獲取邊界框座標 (x1, y1, x2, y2)
                        xyxy = box.xyxy[0].cpu().numpy().astype(int).tolist()
                        
                        detections.append({
                            'label': label,
                            'confidence': conf,
                            'bbox': xyxy  # [x1, y1, x2, y2]
                        })
            
            return detections
            
        except Exception as e:
            print(f"推論過程中發生錯誤: {e}")
            return []

    def draw_detections(self, image, detections, save_path=None):
        """
        在圖片上繪製偵測結果
        
        Args:
            image: OpenCV 圖片
            detections: 偵測結果列表
            save_path: 儲存路徑（可選）
            
        Returns:
            numpy.ndarray: 繪製結果的圖片
        """
        img_draw = image.copy()
        
        for det in detections:
            label = det['label']
            confidence = det['confidence']
            bbox = det['bbox']  # [x1, y1, x2, y2]
            
            x1, y1, x2, y2 = bbox
            
            # 繪製邊界框
            cv2.rectangle(img_draw, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            # 繪製標籤和信心度
            label_text = f"{label} {confidence:.2f}"
            cv2.putText(img_draw, label_text, (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        if save_path:
            cv2.imwrite(save_path, img_draw)
            print(f"結果已儲存至: {save_path}")
            
        return img_draw


def main():
    """
    主要執行函數 - 使用範例
    """
    # =============================================================================
    # !!! 請修改以下路徑以符合您的設定 !!!
    # =============================================================================
    weights_file = "path/to/your/yolov12_weights.pt"  # 您的模型權重檔案路徑
    sample_image = "path/to/your/sample_image.jpg"    # 測試圖片路徑
    output_image_path = "detection_result.jpg"        # 輸出結果路徑
    
    # 檢查檔案是否存在
    if not os.path.exists(weights_file):
        print(f"錯誤：模型權重檔案 '{weights_file}' 不存在。")
        print("請修改 'weights_file' 變數為您 YOLOv12 權重檔案的正確路徑。")
        print("例如：'runs/detect/train/weights/best.pt'")
        return
    
    if not os.path.exists(sample_image):
        print(f"錯誤：範例圖片檔案 '{sample_image}' 不存在。")
        print("請修改 'sample_image' 變數為測試圖片的正確路徑。")
        return
    
    print("=== YOLOv12 物件偵測測試 ===")
    
    # 初始化偵測器
    print("初始化 YOLOv12 偵測器...")
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    detector = YOLOv12Detector(
        weights_path=weights_file, 
        device=device,
        conf_thres=0.25,
        iou_thres=0.45,
        img_size=640
    )
    
    if detector.model is None:
        print("模型初始化失敗，程式結束。")
        return
    
    # 進行偵測
    print(f"\n正在對圖片 '{sample_image}' 進行偵測...")
    detections = detector.detect(sample_image)
    
    if detections:
        print(f"\n偵測到 {len(detections)} 個物件：")
        
        # 讀取原始圖片用於繪製
        img_original = cv2.imread(sample_image)
        
        # 顯示偵測結果
        for i, det in enumerate(detections, 1):
            label = det['label']
            confidence = det['confidence']
            bbox = det['bbox']  # [x1, y1, x2, y2]
            print(f"  {i}. 標籤: {label}, 信心度: {confidence:.3f}, "
                  f"座標: [{bbox[0]}, {bbox[1]}, {bbox[2]}, {bbox[3]}]")
        
        # 繪製並儲存結果
        result_img = detector.draw_detections(img_original, detections, output_image_path)
        
        print(f"\n偵測完成！結果已儲存至: {output_image_path}")
        
        # 可選：顯示結果（需要 GUI 環境）
        # cv2.imshow("Detection Result", result_img)
        # cv2.waitKey(0)
        # cv2.destroyAllWindows()
        
    else:
        print("\n未偵測到任何物件。")
        print("可能原因：")
        print("1. 圖片中沒有模型訓練過的物件")
        print("2. 信心度閾值過高（目前設定為 0.25）")
        print("3. 圖片品質問題")


if __name__ == '__main__':
    main()