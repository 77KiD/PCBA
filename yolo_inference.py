import torch
import cv2
import numpy as np
# import yaml # 如果您的模型使用 .yaml 配置文件

# --- 以下部分需要您根據您的 Yolov12 設定進行修改 ---
# 例如，如果您的 Yolov12 來自某個 GitHub 倉庫，您可能需要導入其中的模型定義
# from your_yolov12_project.models.experimental import attempt_load # 範例
# from your_yolov12_project.utils.general import non_max_suppression # 範例
# from your_yolov12_project.utils.torch_utils import select_device # 範例

class YOLOv12Detector:
    def __init__(self, weights_path, device='cpu', img_size=640, conf_thres=0.25, iou_thres=0.45):
        """
        初始化 YOLOv12 物件偵測器。

        Args:
            weights_path (str): 模型權重檔案的路徑 (例如 'path/to/your/best.pt')。
            device (str): 推論設備 ('cpu' 或 'cuda:0')。
            img_size (int): 模型期望的輸入圖片大小。
            conf_thres (float): 物件信心度閾值。
            iou_thres (float): NMS (非極大值抑制) 的 IoU 閾值。
        """
        self.device = torch.device(device)
        # self.device = select_device(device) # 如果使用 Ultralytics 風格的工具
        self.img_size = img_size
        self.conf_thres = conf_thres
        self.iou_thres = iou_thres

        # 載入模型
        # ---------------------------------------------------------------------
        # !!! 關鍵部分：您需要在此處填寫載入模型的實際程式碼 !!!
        # 這完全取決於您的 Yolov12 如何定義和載入模型。
        #
        # 範例1 (如果您的模型是一個 PyTorch nn.Module 並且可以直接載入 state_dict):
        # self.model = YourModelClass(*args, **kwargs) # 假設您有模型定義的類別
        # self.model.load_state_dict(torch.load(weights_path, map_location=self.device)['model'].float().state_dict())

        # 範例2 (如果使用類似 Ultralytics 的 attempt_load):
        # self.model = attempt_load(weights_path, map_location=self.device)
        # self.model.to(self.device).eval()
        # if self.device.type != 'cpu': # 半精度 (FP16) 僅在 GPU 上支持
        #    self.model.half()

        # 範例3 (如果使用 torch.hub.load):
        # self.model = torch.hub.load('ultralytics/yolov5', 'custom', path=weights_path, device=device)
        #
        # 請替換以下示意性程式碼
        try:
            # 這是示意，您幾乎肯定需要修改這裡
            print(f"正在嘗試從 {weights_path} 載入模型...")
            # 假設您的模型是 torch.jit.ScriptModule 或可以直接載入
            # self.model = torch.jit.load(weights_path, map_location=self.device)
            # 或者，如果它是一個 state_dict
            # self.model = ... # 初始化您的模型架構
            # self.model.load_state_dict(torch.load(weights_path, map_location=self.device))
            self.model = None # Placeholder
            if self.model is None: # 強制提醒需要實現模型載入
                 raise NotImplementedError("模型載入邏輯尚未實現。請在 yolo_inference.py 中根據您的 Yolov12 設定修改此部分。")
            self.model.to(self.device).eval()
            if self.device.type != 'cpu' and hasattr(self.model, 'half'): # 檢查是否有 half 方法
                 self.model.half() # 使用半精度以加速
            print("模型載入成功 (示意)。")
        except Exception as e:
            print(f"錯誤：載入模型失敗。{e}")
            print("請確保您已在 yolo_inference.py 中正確實現了模型載入邏輯。")
            self.model = None
        # ---------------------------------------------------------------------

        # 獲取類別名稱 (如果可用)
        # self.names = self.model.module.names if hasattr(self.model, 'module') else self.model.names # Ultralytics 風格

    def preprocess_image(self, img0):
        """
        對輸入圖片進行預處理。

        Args:
            img0 (numpy.ndarray): 從 cv2.imread() 讀取的原始圖片 (BGR 格式)。

        Returns:
            torch.Tensor: 預處理後的圖片張量。
            numpy.ndarray: 原始圖片的副本。
        """
        # Padded resize
        img = letterbox(img0, self.img_size, stride=32)[0] # 假設 stride=32

        # Convert
        img = img[:, :, ::-1].transpose(2, 0, 1)  # BGR to RGB, HWC to CHW
        img = np.ascontiguousarray(img)
        return torch.from_numpy(img).to(self.device), img0

    def detect(self, image_path_or_cv2_frame):
        """
        使用 Yolov12 模型對單張圖片進行物件偵測。

        Args:
            image_path_or_cv2_frame (str or numpy.ndarray): 圖片的路徑或 OpenCV 讀取的 frame。

        Returns:
            list: 偵測結果的列表。每個結果是一個字典，包含 'label', 'confidence', 'bbox' (x1, y1, x2, y2)。
                  如果模型未載入或推論失敗，則返回空列表。
        """
        if self.model is None:
            print("錯誤：模型尚未載入。")
            return []

        if isinstance(image_path_or_cv2_frame, str):
            img0 = cv2.imread(image_path_or_cv2_frame)  # BGR
            if img0 is None:
                print(f"錯誤：無法讀取圖片 {image_path_or_cv2_frame}")
                return []
        elif isinstance(image_path_or_cv2_frame, np.ndarray):
            img0 = image_path_or_cv2_frame # 假設傳入的是 cv2 frame (BGR)
        else:
            print("錯誤：輸入必須是圖片路徑或 OpenCV frame。")
            return []

        # 預處理
        img, _ = self.preprocess_image(img0.copy()) # img0.copy() 以避免修改原始 frame
        img = img.half() if self.device.type != 'cpu' and hasattr(self.model, 'half') else img.float()  # uint8 to fp16/32
        img /= 255.0  # 0 - 255 to 0.0 - 1.0
        if img.ndimension() == 3:
            img = img.unsqueeze(0) # 擴展 batch 維度

        # 推論
        with torch.no_grad():
            pred = self.model(img, augment=False)[0] # augment=False 是 Ultralytics 風格的參數

        # 進行 NMS (非極大值抑制)
        # ---------------------------------------------------------------------
        # !!! 關鍵部分：您需要在此處填寫 NMS 的實際程式碼 !!!
        # 這也取決於您的 Yolov12 框架如何處理輸出和 NMS。
        #
        # 範例 (Ultralytics 風格):
        # pred = non_max_suppression(pred, self.conf_thres, self.iou_thres, classes=None, agnostic=False)
        #
        # 請替換以下示意性程式碼
        # 這裡的 pred 格式是假設的，您需要根據您的模型實際輸出進行調整
        # 假設 pred 是一個 [N, 5 + num_classes] 的張量，其中 N 是偵測到的框數量
        # 每行是 [x_center, y_center, width, height, object_confidence, class1_score, class2_score, ...]
        # 以下是一個非常簡化的 NMS 示意，實際中您應該使用更完善的 NMS 實現
        detections = [] # 最終的偵測結果
        # for det in pred: # 假設 pred 是經過 NMS 處理後的列表
        #    if det is not None and len(det):
        #        # Rescale boxes from img_size to img0 size
        #        det[:, :4] = scale_coords(img.shape[2:], det[:, :4], img0.shape).round()
        #        for *xyxy, conf, cls in reversed(det):
        #            label = f'{self.names[int(cls)]}'
        #            detections.append({
        #                'label': label,
        #                'confidence': conf.item(),
        #                'bbox': [int(c.item()) for c in xyxy] # x1, y1, x2, y2
        #            })
        # ---------------------------------------------------------------------
        if not hasattr(self, 'non_max_suppression_implemented') or not self.non_max_suppression_implemented:
            print("警告：NMS (非極大值抑制) 邏輯尚未完全實現或未適配您的模型輸出。")
            print("目前的推論結果可能不準確或包含大量重疊的邊界框。")
            print("請在 yolo_inference.py 的 detect 方法中根據您的 Yolov12 設定修改 NMS 部分。")
            # 作為臨時措施，我們可以嘗試解析原始輸出，但這非常依賴模型輸出格式
            # 這裡僅為示意，您需要根據您的模型輸出進行調整
            for i in range(pred.size(0)): # 遍歷 batch (雖然我們通常 batch_size=1)
                for j in range(pred.size(1)): # 遍歷偵測
                    instance = pred[i, j, :]
                    obj_conf = instance[4]
                    if obj_conf > self.conf_thres:
                        class_scores = instance[5:]
                        class_id = torch.argmax(class_scores)
                        class_conf = class_scores[class_id]
                        total_conf = obj_conf * class_conf
                        if total_conf > self.conf_thres:
                            # 假設 self.names 是一個類別名稱列表
                            label = str(int(class_id.item())) # 如果沒有 self.names，則使用類別索引
                            # if hasattr(self, 'names') and self.names:
                            # label = self.names[int(class_id.item())]

                            # 這裡的 bbox 格式轉換也需要根據您的模型輸出 (xywh 或 xyxy) 進行調整
                            # 假設是 xywh 且是相對於整個圖片的比例
                            box_x_center, box_y_center, box_w, box_h = instance[0:4] * self.img_size
                            x1 = int(box_x_center - box_w / 2)
                            y1 = int(box_y_center - box_h / 2)
                            x2 = int(box_x_center + box_w / 2)
                            y2 = int(box_y_center + box_h / 2)
                            # 根據 letterbox 調整座標 (如果需要)
                            detections.append({
                                'label': label,
                                'confidence': total_conf.item(),
                                'bbox': [x1,y1,x2,y2] # x1, y1, x2, y2
                            })


        return detections

# 輔助函數 (通常來自 Yolov12 專案的 utils)
def letterbox(img, new_shape=(640, 640), color=(114, 114, 114), auto=True, scaleFill=False, scaleup=True, stride=32):
    # Resize and pad image while meeting stride-multiple constraints
    shape = img.shape[:2]  # current shape [height, width]
    if isinstance(new_shape, int):
        new_shape = (new_shape, new_shape)

    # Scale ratio (new / old)
    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
    if not scaleup:  # only scale down, do not scale up (for better test mAP)
        r = min(r, 1.0)

    # Compute padding
    ratio = r, r  # width, height ratios
    new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
    dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]  # wh padding
    if auto:  # minimum rectangle
        dw, dh = np.mod(dw, stride), np.mod(dh, stride)  # wh padding
    elif scaleFill:  # stretch
        dw, dh = 0.0, 0.0
        new_unpad = (new_shape[1], new_shape[0])
        ratio = new_shape[1] / shape[1], new_shape[0] / shape[0]  # width, height ratios

    dw /= 2  # divide padding into 2 sides
    dh /= 2

    if shape[::-1] != new_unpad:  # resize
        img = cv2.resize(img, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)  # add border
    return img, ratio, (dw, dh)

def scale_coords(img1_shape, coords, img0_shape, ratio_pad=None):
    # Rescale coords (xyxy) from img1_shape to img0_shape
    if ratio_pad is None:  # calculate from img0_shape
        gain = min(img1_shape[0] / img0_shape[0], img1_shape[1] / img0_shape[1])  # gain  = old / new
        pad = (img1_shape[1] - img0_shape[1] * gain) / 2, (img1_shape[0] - img0_shape[0] * gain) / 2  # wh padding
    else:
        gain = ratio_pad[0][0]
        pad = ratio_pad[1]

    coords[:, [0, 2]] -= pad[0]  # x padding
    coords[:, [1, 3]] -= pad[1]  # y padding
    coords[:, :4] /= gain
    clip_coords(coords, img0_shape)
    return coords

def clip_coords(boxes, img_shape):
    # Clip bounding xyxy bounding boxes to image shape (height, width)
    boxes[:, 0].clamp_(0, img_shape[1])  # x1
    boxes[:, 1].clamp_(0, img_shape[0])  # y1
    boxes[:, 2].clamp_(0, img_shape[1])  # x2
    boxes[:, 3].clamp_(0, img_shape[0])  # y2


if __name__ == '__main__':
    # --- 使用範例 ---
    # !!! 您需要修改以下路徑和參數以符合您的設定 !!!
    weights_file = "path/to/your/yolov12_weights.pt" # <--- 修改這裡
    sample_image = "path/to/your/sample_image.jpg"   # <--- 修改這裡 (或使用 camera_capture.py 產生的圖片)
    output_image_path = "detection_result.jpg"

    # 檢查權重檔案是否存在
    import os
    if not os.path.exists(weights_file):
        print(f"錯誤：模型權重檔案 '{weights_file}' 不存在。")
        print("請修改 'weights_file' 變數為您 Yolov12 權重檔案的正確路徑。")
        print("例如：'YOLO12/runs/detect/pcb_yolo12x_50epochs/weights/best.pt'")
        exit()

    # 檢查範例圖片是否存在
    if not os.path.exists(sample_image):
        print(f"錯誤：範例圖片檔案 '{sample_image}' 不存在。")
        print("請修改 'sample_image' 變數為一張測試圖片的正確路徑。")
        exit()

    print("初始化 Yolov12 偵測器...")
    # 根據您的情況選擇 'cpu' 或 'cuda' (如果 GPU 可用且 PyTorch 已正確安裝 CUDA 版本)
    detector = YOLOv12Detector(weights_path=weights_file, device='cpu') # 或者 'cuda'

    if detector.model is not None:
        print(f"正在對圖片 '{sample_image}' 進行偵測...")
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
                cv2.rectangle(img_to_draw, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(img_to_draw, f"{label} {confidence:.2f}", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            cv2.imwrite(output_image_path, img_to_draw)
            print(f"\n已將帶有偵測結果的圖片保存到: {output_image_path}")
            # cv2.imshow("Detection Result", img_to_draw)
            # cv2.waitKey(0)
            # cv2.destroyAllWindows()
        else:
            print("未偵測到任何物件，或推論過程中發生錯誤。")
    else:
        print("模型未能成功初始化，無法進行偵測。")
