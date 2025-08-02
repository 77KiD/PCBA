import torch
import cv2
import numpy as np
import os
from ultralytics import YOLO

class YOLOv12Detector:
    def __init__(self, weights_path, device='cpu'):
        """
        初始化 YOLOv12 物件偵測器 (使用 Ultralytics 框架)。

        Args:
            weights_path (str): 模型權重檔案的路徑 (例如 'path/to/your/best.pt')。
            device (str): 推論設備 ('cpu' 或 'cuda')。Ultralytics 會自動處理。
        """
        self.device = device
        self.model = None
        self.names = {}

        if not os.path.exists(weights_path):
            print(f"錯誤：模型權重檔案不存在於 '{weights_path}'。")
            print("請在 main.py 中設定正確的 YOLO_WEIGHTS_PATH。")
            # 即使檔案不存在，也初始化物件，但在 detect 時會返回空列表
            return

        try:
            print(f"正在從 '{weights_path}' 載入 Ultralytics YOLO 模型...")
            # 使用 Ultralytics 的 YOLO 類別載入模型。它會自動處理設備分配。
            self.model = YOLO(weights_path)
            self.model.to(self.device)
            # 獲取類別名稱
            self.names = self.model.names
            print("Ultralytics YOLO 模型載入成功。")
            print(f"模型類別: {self.names}")

        except Exception as e:
            print(f"錯誤：載入 Ultralytics YOLO 模型失敗。{e}")
            print("請確保 'ultralytics' 套件已安裝，且權重檔案格式正確。")
            self.model = None

    def detect(self, image_path_or_cv2_frame, conf_thres=0.25, iou_thres=0.45):
        """
        使用 Yolov12 模型對單張圖片进行物件偵測。

        Args:
            image_path_or_cv2_frame (str or numpy.ndarray): 圖片的路徑或 OpenCV 讀取的 frame。
            conf_thres (float): 物件信心度閾值。
            iou_thres (float): NMS (非極大值抑制) 的 IoU 閾值。

        Returns:
            list: 偵測結果的列表。每個結果是一個字典，包含 'label', 'confidence', 'bbox' (x1, y1, x2, y2)。
                  如果模型未載入或推論失敗，則返回空列表。
        """
        if self.model is None:
            print("錯誤：YOLO 模型尚未成功載入，無法進行偵測。")
            return []

        try:
            # Ultralytics 的 predict 方法接受多種輸入格式，包括檔案路徑和 numpy 陣列
            # 它會自動處理預處理、推論和 NMS
            results = self.model.predict(source=image_path_or_cv2_frame,
                                         conf=conf_thres,
                                         iou=iou_thres,
                                         device=self.device,
                                         verbose=False) # 減少控制台輸出

            detections = []
            # results 是一個列表，通常只包含一個結果物件 (因為我們一次只處理一張圖片)
            result = results[0]

            # 將偵測結果轉換為我們需要的格式
            for box in result.boxes:
                class_id = int(box.cls)
                label = self.names.get(class_id, f"class_{class_id}")
                confidence = float(box.conf)
                bbox_tensor = box.xyxy[0] # 獲取 (x1, y1, x2, y2) 張量

                detections.append({
                    'label': label,
                    'confidence': confidence,
                    'bbox': [int(c) for c in bbox_tensor] # 轉換為整數列表
                })

            # 按信心度降序排序
            detections.sort(key=lambda x: x['confidence'], reverse=True)

            return detections

        except Exception as e:
            print(f"YOLO 推論過程中發生錯誤: {e}")
            return []

if __name__ == '__main__':
    # --- 使用範例 ---
    # !!! 您需要修改以下路徑和參數以符合您的設定 !!!

    # 1. 設定您的模型權重檔案路徑
    #    在實際專案中，這個路徑應該由 main.py 傳入
    weights_file = "path/to/your/yolov12_weights.pt" # <--- 修改這裡

    # 2. 設定一張用於測試的範例圖片
    sample_image = "path/to/your/sample_image.jpg"   # <--- 修改這裡
    output_image_path = "detection_result.jpg"

    # --- 前置檢查 ---
    if 'path/to/your' in weights_file:
        print("="*50)
        print("!!! 提示：請先修改 'yolo_inference.py' 中的 'weights_file' 變數 !!!")
        print(f"目前的權重路徑是: '{weights_file}'")
        print("請將其指向您訓練好的 .pt 模型檔案。")
        print("="*50)
        exit()

    if not os.path.exists(weights_file):
        print(f"錯誤：模型權重檔案 '{weights_file}' 不存在。")
        exit()

    if 'path/to/your' in sample_image or not os.path.exists(sample_image):
        print("="*50)
        print("!!! 提示：請先修改 'yolo_inference.py' 中的 'sample_image' 變數 !!!")
        print(f"目前的圖片路徑是: '{sample_image}'")
        print("請將其指向一張您想要測試的圖片。")
        print("="*50)
        # 如果找不到範例圖片，嘗試從攝影機擷取一張
        print("\n找不到範例圖片，嘗試使用攝影機擷取一張作為測試...")
        try:
            from camera_capture import capture_image
            sample_image = capture_image(output_dir="captured_images", filename_prefix="yolo_test")
            if not sample_image:
                 print("攝影機擷取失敗，測試無法繼續。")
                 exit()
            print(f"已使用攝影機擷取圖片: {sample_image}")
        except ImportError:
            print("找不到 camera_capture.py，無法自動擷取圖片。")
            exit()
        except Exception as e:
            print(f"使用攝影機擷取圖片時發生錯誤: {e}")
            exit()

    # --- 執行偵測 ---
    print("\n初始化 YOLOv12 偵測器...")
    # 根據您的情況選擇 'cpu' 或 'cuda'
    detector = YOLOv12Detector(weights_path=weights_file, device='cuda' if torch.cuda.is_available() else 'cpu')

    if detector.model is not None:
        print(f"\n正在對圖片 '{sample_image}' 進行偵測...")
        detections = detector.detect(sample_image)

        if detections:
            print(f"\n偵測到 {len(detections)} 個物件：")
            img_to_draw = cv2.imread(sample_image)
            for det in detections:
                label = det['label']
                confidence = det['confidence']
                bbox = det['bbox'] # x1, y1, x2, y2
                print(f"  - 標籤: {label}, 信心度: {confidence:.2f}, 邊界框: {bbox}")

                # 在圖片上繪製邊界框和標籤
                x1, y1, x2, y2 = bbox
                # 根據標籤給定不同顏色 (可選)
                color = (0, 255, 0) # 預設為綠色
                cv2.rectangle(img_to_draw, (x1, y1), (x2, y2), color, 2)

                label_text = f"{label} {confidence:.2f}"
                (w, h), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                cv2.rectangle(img_to_draw, (x1, y1 - h - 15), (x1 + w, y1 - 5), color, -1)
                cv2.putText(img_to_draw, label_text, (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            cv2.imwrite(output_image_path, img_to_draw)
            print(f"\n已將帶有偵測結果的圖片保存到: {output_image_path}")
            print("您可以打開該圖片查看結果。")
        else:
            print("未偵測到任何物件，或推論過程中發生錯誤。")
    else:
        print("模型未能成功初始化，無法進行偵測。")
