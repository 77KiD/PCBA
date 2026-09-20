# 🔬 PCB 瑕疵檢測系統

<div align="center">

![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python&logoColor=white)
![YOLOv12](https://img.shields.io/badge/YOLOv12-Ultralytics-purple?logo=pytorch)
![PyQt5](https://img.shields.io/badge/PyQt5-GUI-green?logo=qt)
![Arduino](https://img.shields.io/badge/Arduino-UNO%20%7C%20Nano-teal?logo=arduino)
![OpenCV](https://img.shields.io/badge/OpenCV-Vision-red?logo=opencv)

**結合 YOLOv12 AI 視覺辨識與六軸機械手臂的 PCB 瑕疵自動檢測分類系統**

</div>

---

## 📖 專案簡介

本系統針對印刷電路板（PCB）的生產品管流程，整合深度學習模型與機械手臂自動化，實現三類瑕疵的即時辨識與自動分類：

| 瑕疵類型 | 英文 | 說明 |
|----------|------|------|
| 🐭 **鼠咬** | Mouse Bite | 電路板邊緣或銅箔遭鑽孔缺口破壞 |
| ⚡ **斷路** | Open Circuit | 導線斷裂，電流無法正常通過 |
| 🟡 **雜銅** | Copper Contamination | 多餘銅殘留造成短路風險 |

系統依據檢測到的**瑕疵種類數量**進行分級：
- **合格** — 未偵測到缺陷
- **單一瑕疵** — 偵測到 1 種缺陷
- **兩種瑕疵** — 偵測到 2 種缺陷
- **多種瑕疵** — 偵測到 3 種以上缺陷

---

## 🏗️ 系統架構

```
┌─────────────────────────────────────────────────────────────────┐
│                        PCB 瑕疵檢測系統                          │
│                                                                 │
│  ┌──────────────┐     ┌──────────────┐     ┌────────────────┐  │
│  │  傳送帶系統   │────▶│  IR 感應器1  │────▶│  USB 相機拍照  │  │
│  │  (輸送 PCB)  │     │  觸發拍照     │     │  640×480 / 30fps│  │
│  └──────────────┘     └──────────────┘     └───────┬────────┘  │
│                                                     │           │
│                        ┌────────────────────────────▼────────┐  │
│                        │    YOLOv12 瑕疵檢測引擎 (best.pt)   │  │
│                        │    鼠咬 / 斷路 / 雜銅  三類辨識      │  │
│                        └────────────────────────────┬────────┘  │
│                                                     │           │
│  ┌──────────────┐     ┌──────────────┐     ┌───────▼────────┐  │
│  │ 六軸機械手臂 │◀────│  IR 感應器2  │◀────│   分類結果輸出  │  │
│  │  (自動分類)  │     │  觸發分類     │     │  合格/單/雙/多  │  │
│  └──────────────┘     └──────────────┘     └────────────────┘  │
│                                                                 │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              PyQt5 控制介面 (Dark Theme)                    │ │
│  │   即時影像 │ 檢測結果 │ 手臂控制 │ 歷史紀錄 │ 系統設定     │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘

硬體通訊層：
  Arduino UNO  ──(USB Serial / CH340)──▶  IR 感應器 + 傳送帶繼電器
  Arduino Nano ──(USB Serial)──────────▶  六軸舵機手臂 (Pin 4~9)
```

---

## 🔧 硬體需求

### 主控電腦
- **OS**：Windows 10+ / Ubuntu 20.04+ / NVIDIA Jetson (支援)
- **Python**：3.8 以上
- **GPU**：選配（推薦 NVIDIA GPU 加速 YOLO 推論）

### Arduino 控制器

| 控制器 | 型號 | 功能 | 串口晶片 |
|--------|------|------|----------|
| IR 感應器控制器 | Arduino UNO | 控制 TCRT5000 IR 感應器 + 傳送帶繼電器 | CH340 |
| 機械手臂控制器 | Arduino Nano | 控制六軸舵機 | CH340 / FT232 |

### 感測器與執行器

| 元件 | 規格 | 連接 |
|------|------|------|
| IR 感應器 1 | TCRT5000 (AO) | UNO → A0（觸發拍照） |
| IR 感應器 2 | TCRT5000 (AO) | UNO → A1（觸發分類） |
| 傳送帶繼電器 | 5V 繼電器 | UNO → D4 |
| 舵機 Joint 1~6 | 標準舵機 | Nano → D4, D5, D6, D7, D8, D9 |
| USB 相機 | 640×480 / 30fps+ | PC USB |

### 機械手臂關節設定

| 關節 | 角度範圍 | 預設角度 |
|------|----------|----------|
| Joint 1 | 0° ~ 180° | 0° |
| Joint 2 | 0° ~ 180° | 180° |
| Joint 3 | 0° ~ 180° | 90° |
| Joint 4 | 0° ~ 180° | 90° |
| Joint 5 | 0° ~ 180° | 90° |
| Joint 6 (夾爪) | 30° ~ 73° | 73° |

---

## 📦 軟體架構

```
pcb_detection_system_v4/
├── merged_project/
│   ├── pcb_detection_system_complete.py   # 主程式 (PyQt5 GUI 入口)
│   ├── detection_engine.py                # YOLOv12 檢測引擎
│   ├── hardware_controller.py             # 相機硬體管理
│   ├── robotic_arm_controller.py          # 六軸手臂串口控制
│   ├── arm_control_ui.py                  # 手臂控制 UI 元件
│   ├── image_processor.py                 # 影像前處理
│   ├── data_manager.py                    # 檢測紀錄管理
│   ├── config_manager.py                  # 硬體與檢測參數設定
│   ├── install.sh                         # 一鍵安裝腳本
│   ├── best.pt                            # YOLOv12 訓練模型
│   ├── arm_positions.json                 # 手臂預設位置
│   ├── positions.json                     # 手臂儲存位置
│   ├── sequences.json                     # 動作序列設定
│   ├── 感測器UNO/                         # Arduino UNO 韌體
│   │   └── sketch_*.ino                   # IR 感應器 + 繼電器控制
│   └── 機械手臂NANO/                      # Arduino Nano 韌體
│       └── sketch_*.ino                   # 六軸舵機控制
└── best.pt                                # 備份模型檔案
```

---

## ⚙️ 安裝教學

### 方式一：一鍵安裝（推薦）

```bash
cd merged_project
chmod +x install.sh
./install.sh
```

### 方式二：手動安裝

**1. 安裝 Python 依賴**
```bash
pip install PyQt5 opencv-python numpy ultralytics pyserial
```

**2. Jetson Nano 額外安裝（選配）**
```bash
sudo pip3 install Jetson.GPIO
sudo pip3 install adafruit-circuitpython-pca9685 adafruit-circuitpython-motor
```

**3. 燒錄 Arduino 韌體**

使用 Arduino IDE 依序燒錄：

| 韌體檔案 | 目標板 | 說明 |
|----------|--------|------|
| `感測器UNO/sketch_*.ino` | Arduino UNO | IR 感應器 + 繼電器控制 |
| `機械手臂NANO/sketch_*.ino` | Arduino Nano | 六軸舵機控制 |

---

## 🚀 使用方式

### 啟動主程式

```bash
cd merged_project
python3 pcb_detection_system_complete.py
```

啟動時，系統會自動掃描並分配 COM Port：
- **CH340 / WCH 晶片** → 識別為 Arduino UNO（IR 感應器控制）
- **其他串口** → 識別為 Arduino Nano（機械手臂控制）

### 操作流程

```
1. 啟動程式 → 系統自動初始化相機 + 串口
2. 放置 PCB 至傳送帶
3. IR1 感應器觸發 → 傳送帶暫停 → 相機拍照
4. YOLOv12 進行瑕疵檢測 → 輸出分類結果
5. IR2 感應器觸發 → 機械手臂依分類結果進行分料
6. 檢測紀錄自動儲存
```

### 主要功能說明

| 功能頁籤 | 說明 |
|----------|------|
| 📷 即時影像 | 相機即時畫面 + YOLO 框選標示 |
| 📊 檢測結果 | 當前 PCB 的瑕疵類型與信心分數 |
| 🦾 手臂控制 | 手動控制六軸手臂、儲存/執行動作序列 |
| 📋 歷史紀錄 | 檢測數量統計、瑕疵比例圖表 |
| ⚙️ 系統設定 | 檢測閾值、串口設定、硬體參數 |

---

## 🔩 硬體接線圖

### Arduino UNO（感測器控制）

```
TCRT5000 IR1  AO  ──▶  UNO  A0
TCRT5000 IR2  AO  ──▶  UNO  A1
繼電器 IN1        ──▶  UNO  D4
UNO GND           ──▶  系統共地
UNO 5V            ──▶  感測器 VCC
```

### Arduino Nano（手臂控制）

```
舵機 Joint 1  Signal  ──▶  Nano  D4
舵機 Joint 2  Signal  ──▶  Nano  D5
舵機 Joint 3  Signal  ──▶  Nano  D6
舵機 Joint 4  Signal  ──▶  Nano  D7
舵機 Joint 5  Signal  ──▶  Nano  D8
舵機 Joint 6  Signal  ──▶  Nano  D9   (夾爪)
所有舵機 GND          ──▶  共地
所有舵機 VCC          ──▶  5V 外部電源（勿直接用 USB 供電）
```

> ⚠️ **注意**：六軸舵機電流需求較大，請使用外部 5V 電源供應，避免透過 Arduino 直接供電造成褐出（Brownout）。

---

## 🧠 AI 模型

- **架構**：YOLOv12（Ultralytics）
- **模型檔**：`best.pt`
- **辨識類別**：
  - `mouse_bite` / `mousebite` → 鼠咬
  - `open_circuit` / `開放` / `break` → 斷路
  - `copper` / `copper_contamination` → 雜銅
- **預設信心閾值**：0.5（可於系統設定調整）

---

## ⚙️ 系統參數設定

主要可調參數位於 `config_manager.py`：

```python
# 硬體設定
camera_index: int = 0         # 相機編號
camera_width:  int = 640      # 影像寬度
camera_height: int = 480      # 影像高度
camera_fps:    int = 30       # 幀率

# IR 感應器引腳（UNO）
ir1_sensor_pin: int = 23      # IR1 拍照觸發
ir2_sensor_pin: int = 22      # IR2 手臂觸發

# 檢測設定
threshold: float = 0.5        # 瑕疵信心閾值
sorting_delay: float = 0.5    # 分類延遲（秒）
```

---

## 🖥️ 介面預覽

系統採用**深色主題 PyQt5 GUI**，包含：
- 即時影像串流視窗（含 YOLO 標注框）
- 瑕疵統計表格與紀錄匯出
- 六軸手臂視覺化控制介面
- COM Port 自動掃描與分配

---

## 🔄 Jetson 環境支援

在 NVIDIA Jetson 設備上執行，請於主程式開頭設定：

```python
# pcb_detection_system_complete.py 第 7 行
JETSON_ENV = True  # 啟用 Jetson 模式
```

Jetson 環境支援 GPIO 直接控制，提供更低延遲的感測器響應。

---

## 📋 依賴清單

| 套件 | 版本需求 | 用途 |
|------|----------|------|
| Python | ≥ 3.8 | 執行環境 |
| PyQt5 | ≥ 5.15 | GUI 介面 |
| opencv-python | ≥ 4.5 | 影像處理 |
| ultralytics | 最新 | YOLOv12 推論 |
| pyserial | ≥ 3.5 | Arduino 串口通訊 |
| numpy | ≥ 1.21 | 數值運算 |

---

## ⚠️ 常見問題

**Q: 程式啟動後找不到 COM Port？**
> 確認 Arduino 已正確連接，並安裝對應的 CH340 驅動程式。Windows 可至裝置管理員確認。

**Q: 相機無法開啟？**
> 確認 `config_manager.py` 中的 `camera_index` 設定正確（預設 `0`），若有多台相機可嘗試 `1`, `2`...

**Q: YOLO 模型未載入？**
> 確認 `best.pt` 檔案位於 `merged_project/` 目錄下，且已安裝 `ultralytics` 套件。

**Q: 手臂動作不準確？**
> 透過 GUI「手臂控制」頁籤手動調整各關節角度並重新儲存位置序列。

---

## 📄 授權

本專案為學術研究用途，相關演算法與硬體整合方案由 **南台科技大學學生陳治齊** 開發。

---

<div align="center">

**南台科技大學 · 資訊工程系**  
PCB Defect Detection System v4.0

</div>
