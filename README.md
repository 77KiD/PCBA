# PCBA 智能檢測與自動化分類系統

這是一個基於 YOLOv12 物件偵測、輸送帶和六軸機械手臂的 PCBA (印刷電路板) 瑕疵檢測與自動化分類系統。本系統透過圖形化使用者介面 (GUI) 進行操作和監控，專為在 NVIDIA Jetson Orin Nano 平台上運行而設計。

## ✨ 主要功能

- **圖形化使用者介面 (GUI)**: 使用 PyQt5 建立，提供即時影像顯示、狀態監控、參數調整和日誌記錄功能。
- **YOLOv12 物件偵測**: 整合了基於 Ultralytics 框架的 YOLOv12 模型，用於即時瑕疵檢測。
- **輸送帶控制**: 模組化設計，支援 GPIO 和序列 (Serial) 兩種控制方式。
- **六軸機械手臂控制**: 支援透過 `Jetson.GPIO` 函式庫對 MG996R 等伺服馬達進行 PWM 控制，執行物件的夾取和分類放置。
- **模組化設計**: 專案結構清晰，各功能模組（相機、推論、硬體控制）分離，易於維護和擴展。
- **異步處理**: 自動化流程在獨立的 QThread 中運行，確保 GUI 在硬體運作時保持流暢響應。

## 📂 專案結構

```
.
├── weights/
│   └── best.pt           # 您的 YOLOv12 模型權重檔案應放在此處
├── gui_main.py           # ✅ 應用程式主進入點 (啟動此檔案)
├── ui.py                 # PyQt5 UI 介面佈局 (由 Qt Designer 生成或手動編寫)
├── yolo_inference.py     # YOLOv12 推論模組
├── camera_capture.py     # USB 相機影像擷取模組
├── conveyor_control.py   # 輸送帶控制模組
├── robot_arm_control.py  # 機械手臂控制模組
├── requirements.txt      # Python 相依套件列表
├── main.py               # (已棄用) 舊的啟動腳本，會自動導向 gui_main.py
└── README.md             # 本說明檔案
```

## ⚙️ 安裝與設定

### 1. 環境準備

建議使用 Python 虛擬環境。

```bash
# 建立虛擬環境
python3 -m venv .venv

# 啟動虛擬環境 (Linux / macOS)
source .venv/bin/activate

# 啟動虛擬環境 (Windows)
# .venv\Scripts\activate
```

### 2. 安裝相依套件

本專案的大部分相依套件可以透過 `requirements.txt` 安裝。

```bash
pip install -r requirements.txt
```

#### **Jetson Orin Nano 特別注意事項:**

- **PyTorch**: `requirements.txt` 中的 `ultralytics` 會嘗試安裝 PyTorch。然而，在 Jetson 平台上，您需要安裝與您的 JetPack 版本相容的特定 PyTorch `whl` 檔案。請參考 [NVIDIA 官方論壇](https://forums.developer.nvidia.com/t/pytorch-for-jetson/72048) 來獲取正確的安裝指令。
- **Jetson.GPIO**: 這個函式庫通常隨 JetPack 一起安裝。如果未安裝，請執行以下指令：
  ```bash
  sudo -H pip install Jetson.GPIO
  sudo groupadd -f gpio
  sudo usermod -a -G gpio your_username
  ```
  安裝後可能需要**重新啟動** Jetson。

### 3. 硬體與模型配置

這是最關鍵的一步。打開 `gui_main.py` 檔案，您會在檔案頂部找到一個全局配置區塊。

#### **模型配置**
1.  創建一個名為 `weights` 的資料夾。
2.  將您訓練好的 YOLOv12 模型權重檔案 (例如 `best.pt`) 複製到 `weights` 資料夾中。
3.  確認 `YOLO_WEIGHTS_PATH` 變數的路徑正確 (`weights/best.pt`)。

#### **硬體配置**
請根據您的實際硬體連接，修改以下參數：

- **`ARM_PWM_LIB_TYPE`**: 如果您在 Jetson 上運行，請設定為 `"jetson_gpio"`。如果想在沒有硬體的 PC 上進行測試，可以設定為 `"custom"` 以進入示意模式。
- **`ARM_JOINT_PINS`**: 輸入控制 6 個關節伺服馬達的 BCM 腳位號碼列表。
- **`ARM_GRIPPER_PIN`**: 輸入控制夾爪伺服馬達的 BCM 腳位號碼。
- **`CONVEYOR_CONTROL_TYPE`**: 根據您的輸送帶控制方式選擇 `"gpio"` 或 `"serial"`。
- **`CONVEYOR_GPIO_PINS`**: 如果使用 GPIO 控制，請在此處設定 `forward`, `enable`, `sensor` 等腳位的 BCM 編號。
- **`CONVEYOR_SERIAL_PORT`**: 如果使用序列控制 (例如透過 Arduino)，請設定正確的序列埠名稱 (例如 `/dev/ttyUSB0` 或 `COM3`)。

### 4. 機械手臂校準

在 `robot_arm_control.py` 中，有幾個**必須**手動校準的參數，以確保手臂正常運作並防止損壞：

- **`joint_limits`**: 每個關節的最小和最大活動角度。您需要手動測試每個關節的極限，並在此處填寫安全範圍。
- **`gripper_open_angle` / `gripper_closed_angle`**: 夾爪完全張開和閉合時的角度。
- **`predefined_positions`**: 機械手臂的預設姿態，例如 `"home"`, `"pickup"`, `"zone1_drop"` 等。您需要手動示教（移動手臂到指定位置，記錄下每個關節的角度）來獲得這些值。

## 🚀 如何運行

完成所有安裝和配置後，執行以下指令來啟動應用程式：

```bash
python gui_main.py
```

## 🔬 系統工作流程

1.  **初始化**: 系統啟動，初始化所有硬體模組（輸送帶、機械手臂）並載入 YOLO 模型。
2.  **等待觸發**: 系統進入待機狀態。在 `AutomationWorker` 線程中，您可以根據需求實現觸發邏輯（例如，等待光電感測器信號）。
3.  **影像擷取**: 收到觸發信號後，從 USB 相機擷取一張影像。
4.  **影像前處理 (可選)**: 在進行推論前，系統會先對影像進行 Canny 邊緣偵測和高增幅濾波，以強化特徵。此功能可在 `gui_main.py` 中透過 `PREPROCESSING_ENABLED` 開關來啟用或停用。
5.  **YOLO 推論**: 將原始或前處理後的影像送入 YOLOv12 模型進行推論，找出潛在的物件或瑕疵。
6.  **決策**:
    - 如果未偵測到物件，流程結束，等待下一次觸發。
    - 如果偵測到物件，根據信心度最高的物件標籤和 `PRODUCT_TO_ZONE_MAP` 的定義，確定目標分類區域。
6.  **輸送帶移動**: 啟動輸送帶，將產品運送到機械手臂的夾取點。透過感測器或定時來確認產品是否到達。
7.  **機械手臂操作**:
    - 輸送帶停止後，機械手臂執行預設的 `pickup_object` 序列動作。
    - 夾取成功後，手臂移動到目標分類區域，執行 `place_object_in_zone` 序列動作。
    - 完成放置後，手臂返回 `home` 位置。
8.  **循環**: 整個流程結束，系統更新 GUI 上的統計數據和日誌，並準備好處理下一個產品。

---
祝您使用愉快！ 如果遇到問題，請檢查硬體連接和 `gui_main.py` 中的配置是否正確。
