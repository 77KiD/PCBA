# 🔬 PCB Defect Detection System

<div align="center">

**Language / 語言**

[![繁體中文](https://img.shields.io/badge/繁體中文-README.zh--TW.md-red?style=flat-square)](README.zh-TW.md)
[![English](https://img.shields.io/badge/English-README.md-blue?style=flat-square)](README.md)

---

![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python&logoColor=white)
![YOLOv12](https://img.shields.io/badge/YOLOv12-Ultralytics-purple?logo=pytorch)
![PyQt5](https://img.shields.io/badge/PyQt5-GUI-green?logo=qt)
![Arduino](https://img.shields.io/badge/Arduino-UNO%20%7C%20Nano-teal?logo=arduino)
![OpenCV](https://img.shields.io/badge/OpenCV-Vision-red?logo=opencv)

**An automated PCB defect detection and sorting system combining YOLOv12 AI vision with a 6-axis robotic arm**

</div>

---

## 📖 概覽

This system is designed for PCB quality control in production environments. It integrates deep learning inference with robotic arm automation to perform real-time detection and sorting of three PCB defect categories:

| Defect Type |描述|
|-------------|-------------|
| 🐭 **Mouse Bite** | Missing copper at the edge of a PCB caused by drill punch-outs |
| ⚡ **Open Circuit** | Broken trace preventing proper current flow |
| 🟡 **Copper Contamination** | Excess copper residue that creates short-circuit risk |

Boards are graded by the **number of defect types detected**:
- **Pass** — No defects detected
- **Single Defect** — 1 defect type detected
- **Two Defects** — 2 defect types detected
- **Multiple Defects** — 3 or more defect types detected

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   PCB Defect Detection System                   │
│                                                                 │
│  ┌──────────────┐     ┌──────────────┐     ┌────────────────┐  │
│  │   Conveyor   │────▶│  IR Sensor 1 │────▶│  USB Camera    │  │
│  │    System    │     │ Trigger Photo │     │  640×480 / 30fps│  │
│  └──────────────┘     └──────────────┘     └───────┬────────┘  │
│                                                     │           │
│                        ┌────────────────────────────▼────────┐  │
│                        │   YOLOv12 Detection Engine (best.pt) │  │
│                        │   Mouse Bite / Open Circuit / Copper  │  │
│                        └────────────────────────────┬────────┘  │
│                                                     │           │
│  ┌──────────────┐     ┌──────────────┐     ┌───────▼────────┐  │
│  │  6-Axis Arm  │◀────│  IR Sensor 2 │◀────│  Grade Output  │  │
│  │  (Sorting)   │     │ Trigger Sort  │     │ Pass/S/D/Multi │  │
│  └──────────────┘     └──────────────┘     └────────────────┘  │
│                                                                 │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │            PyQt5 Control Interface (Dark Theme)            │ │
│  │   Live Feed │ Results │ Arm Control │ History │ Settings   │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘

Communication Layer:
  Arduino UNO  ──(USB Serial / CH340)──▶  IR Sensors + Conveyor Relay
  Arduino Nano ──(USB Serial)──────────▶  6-Axis Servo Arm (Pins 4–9)
```

---

## 🔧 Hardware Requirements

### Host Computer
- **OS**: Windows 10+ / Ubuntu 20.04+ / NVIDIA Jetson (supported)
- **Python**: 3.8+
- **GPU**: Optional (recommended for faster YOLO inference)

### Arduino Controllers

| Controller | Board | Function | Serial Chip |
|------------|-------|----------|-------------|
| Sensor Controller | Arduino UNO | TCRT5000 IR sensors + conveyor relay | CH340 |
| Arm Controller | Arduino Nano | 6-axis servo control | CH340 / FT232 |

### Sensors & Actuators

| Component | Spec | Connection |
|-----------|------|------------|
| IR Sensor 1 | TCRT5000 (AO) | UNO → A0 (photo trigger) |
| IR Sensor 2 | TCRT5000 (AO) | UNO → A1 (sort trigger) |
| Conveyor Relay | 5V relay | UNO → D4 |
| Servo Joint 1–6 | Standard servo | Nano → D4, D5, D6, D7, D8, D9 |
| USB Camera | 640×480 / 30fps+ | PC USB |

### Robotic Arm Joint Configuration

| Joint | Range | Default |
|-------|-------|---------|
| Joint 1 | 0° – 180° | 0° |
| Joint 2 | 0° – 180° | 180° |
| Joint 3 | 0° – 180° | 90° |
| Joint 4 | 0° – 180° | 90° |
| Joint 5 | 0° – 180° | 90° |
| Joint 6 (Gripper) | 30° – 73° | 73° |

---

## 📦 Project Structure

```
pcb_detection_system_v4/
├── merged_project/
│   ├── pcb_detection_system_complete.py   # Main application (PyQt5 entry point)
│   ├── detection_engine.py                # YOLOv12 detection engine
│   ├── hardware_controller.py             # Camera hardware manager
│   ├── robotic_arm_controller.py          # 6-axis arm serial controller
│   ├── arm_control_ui.py                  # Arm control UI widget
│   ├── image_processor.py                 # Image preprocessing
│   ├── data_manager.py                    # Detection record management
│   ├── config_manager.py                  # Hardware & detection config
│   ├── install.sh                         # One-click install script
│   ├── best.pt                            # YOLOv12 trained model weights
│   ├── arm_positions.json                 # Default arm positions
│   ├── positions.json                     # Saved arm positions
│   ├── sequences.json                     # Motion sequence config
│   ├── 感測器UNO/                         # Arduino UNO firmware
│   │   └── sketch_*.ino                   # IR sensor + relay control
│   └── 機械手臂NANO/                      # Arduino Nano firmware
│       └── sketch_*.ino                   # 6-axis servo control
└── best.pt                                # Backup model weights
```

---

## ⚙️ Installation

### Option 1: One-Click Script (Recommended)

```bash
cd merged_project
chmod +x install.sh
./install.sh
```

### Option 2: Manual Installation

**1. Install Python dependencies**
```bash
pip install PyQt5 opencv-python numpy ultralytics pyserial
```

**2. Jetson Nano additional packages (optional)**
```bash
sudo pip3 install Jetson.GPIO
sudo pip3 install adafruit-circuitpython-pca9685 adafruit-circuitpython-motor
```

**3. Flash Arduino Firmware**

Open Arduino IDE and flash each board:

| Firmware | Target Board | Purpose |
|----------|--------------|---------|
| `感測器UNO/sketch_*.ino` | Arduino UNO | IR sensors + relay |
| `機械手臂NANO/sketch_*.ino` | Arduino Nano | 6-axis servo arm |

---

## 🚀 Usage

### Launch

```bash
cd merged_project
python3 pcb_detection_system_complete.py
```

On startup, the system auto-scans and assigns COM Ports:
- **CH340 / WCH chip** → Arduino UNO (IR sensor control)
- **Other serial ports** → Arduino Nano (robotic arm control)

### Workflow

```
1. Launch app  → Camera + serial ports auto-initialized
2. Place PCB on conveyor belt
3. IR Sensor 1 triggers → Conveyor stops → Camera captures image
4. YOLOv12 detects defects → Grade result output
5. IR Sensor 2 triggers → Robotic arm sorts PCB by grade
6. Detection record auto-saved
```

### Interface Tabs

| Tab | Description |
|-----|-------------|
| 📷 Live Feed | Real-time camera stream with YOLO bounding boxes |
| 📊 Results | Current PCB defect types and confidence scores |
| 🦾 Arm Control | Manual 6-axis control, save/run motion sequences |
| 📋 History | Detection count stats and defect ratio charts |
| ⚙️ Settings | Detection threshold, serial port config, hardware params |

---

## 🔩 Wiring Diagram

### Arduino UNO (Sensor Control)

```
TCRT5000 IR1  AO  ──▶  UNO  A0
TCRT5000 IR2  AO  ──▶  UNO  A1
Relay IN1         ──▶  UNO  D4
UNO GND           ──▶  Common GND
UNO 5V            ──▶  Sensor VCC
```

### Arduino Nano (Arm Control)

```
Servo Joint 1  Signal  ──▶  Nano  D4
Servo Joint 2  Signal  ──▶  Nano  D5
Servo Joint 3  Signal  ──▶  Nano  D6
Servo Joint 4  Signal  ──▶  Nano  D7
Servo Joint 5  Signal  ──▶  Nano  D8
Servo Joint 6  Signal  ──▶  Nano  D9   (Gripper)
All Servos GND         ──▶  Common GND
All Servos VCC         ──▶  External 5V power supply
```

> ⚠️ **Warning**: Six servos draw significant current. Use an external 5V power supply — do **not** power servos directly from Arduino USB power to avoid brownout.

---

## 🧠 AI Model

- **Architecture**: YOLOv12 (Ultralytics)
- **Weights file**: `best.pt`
- **Detection classes**:
  - `mouse_bite` / `mousebite` → Mouse Bite
  - `open_circuit` / `open` / `break` → Open Circuit
  - `copper` / `copper_contamination` → Copper Contamination
- **Default confidence threshold**: 0.5 (adjustable in Settings)

---

## ⚙️ Configuration

Key parameters in `config_manager.py`:

```python
# Hardware
camera_index: int = 0         # Camera device index
camera_width:  int = 640      # Frame width
camera_height: int = 480      # Frame height
camera_fps:    int = 30       # Frame rate

# IR Sensor Pins (UNO)
ir1_sensor_pin: int = 23      # IR1 photo trigger
ir2_sensor_pin: int = 22      # IR2 arm trigger

# Detection
threshold: float = 0.5        # Defect confidence threshold
sorting_delay: float = 0.5    # Sort delay in seconds
```

---

## 🔄 Jetson Support

To run on NVIDIA Jetson, set the flag at line 7 of the main script:

```python
# pcb_detection_system_complete.py
JETSON_ENV = True  # Enable Jetson mode
```

Jetson mode enables direct GPIO control for lower-latency sensor response.

---

## 📋 Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| Python | ≥ 3.8 | Runtime |
| PyQt5 | ≥ 5.15 | GUI framework |
| opencv-python | ≥ 4.5 | Image processing |
| ultralytics | latest | YOLOv12 inference |
| pyserial | ≥ 3.5 | Arduino serial comms |
| numpy | ≥ 1.21 | Numerical computation |

---

## ❓ FAQ

**Q: No COM Port detected on startup?**
> Ensure Arduino is connected and CH340 drivers are installed. On Windows, check Device Manager.

**Q: Camera won't open?**
> Verify `camera_index` in `config_manager.py` (default `0`). Try `1`, `2`... if multiple cameras are connected.

**Q: YOLO model not loading?**
> Confirm `best.pt` is in the `merged_project/` directory and `ultralytics` is installed.

**Q: Arm movement inaccurate?**
> Use the "Arm Control" tab in the GUI to manually adjust joint angles and re-save position sequences.

---

## 📄 License

This project was developed for academic research purposes by the **Southern Taiwan University of Science and Technology · Student Chen Zhiqi** research.

---

<div align="center">

**Southern Taiwan University of Science and Technology · Student Chen Zhiqi**  
PCB Defect Detection System v4.0

</div>
