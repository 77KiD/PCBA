#!/bin/bash

echo "=========================================="
echo "PCB缺陷檢測系統 v3.0 - 安裝腳本"
echo "=========================================="
echo ""

# 檢查Python版本
echo "🔍 檢查Python版本..."
python3 --version

if [ $? -ne 0 ]; then
    echo "❌ 找不到Python3,請先安裝Python 3.8+"
    exit 1
fi

echo ""
echo "📦 安裝基本依賴..."
pip3 install --upgrade pip

echo ""
echo "📦 安裝PyQt5..."
pip3 install PyQt5

echo ""
echo "📦 安裝OpenCV..."
pip3 install opencv-python

echo ""
echo "📦 安裝NumPy..."
pip3 install numpy

echo ""
echo "📦 安裝Ultralytics (YOLOv8/YOLOv12)..."
pip3 install ultralytics

echo ""
echo "=========================================="
echo "🎉 基本依賴安裝完成!"
echo "=========================================="
echo ""

# 檢查是否為Jetson環境
if [ -f "/etc/nv_tegra_release" ]; then
    echo "🤖 檢測到Jetson環境,安裝額外依賴..."
    echo ""
    
    echo "📦 安裝Jetson.GPIO..."
    sudo pip3 install Jetson.GPIO
    
    echo "📦 安裝Adafruit庫..."
    sudo pip3 install adafruit-circuitpython-pca9685
    sudo pip3 install adafruit-circuitpython-motor
    
    echo ""
    echo "✅ Jetson環境依賴安裝完成!"
else
    echo "💻 檢測到一般PC環境"
    echo "⚠️  注意:GPIO功能將以模擬模式運行"
fi

echo ""
echo "=========================================="
echo "✅ 安裝完成!"
echo "=========================================="
echo ""
echo "📋 下一步:"
echo "  1. 確保YOLOv12模型檔案 (best.pt) 在程式目錄"
echo "  2. 執行: python3 pcb_detection_system_complete.py"
echo ""
echo "📖 詳細說明請參考 README.md"
echo ""
