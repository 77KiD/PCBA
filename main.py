# main.py
import time
import os

# 導入我們之前創建的模組
from camera_capture import capture_image
from yolo_inference import YOLOv12Detector # 假設 YOLOv12Detector 類已準備好
from conveyor_control import ConveyorControl # 假設 ConveyorControl 類已準備好
from robot_arm_control import RobotArmControl # 假設 RobotArmControl 類已準備好

# --- 配置參數 ---
# Yolov12 模型權重路徑 (!!!需要您修改!!!)
YOLO_WEIGHTS_PATH = "path/to/your/yolov12_weights.pt"
# 例如: YOLO_WEIGHTS_PATH = "YOLO12/runs/detect/pcb_yolo12x_50epochs/weights/best.pt"
if not os.path.exists(YOLO_WEIGHTS_PATH):
    print(f"警告：YOLO 模型權重檔案 '{YOLO_WEIGHTS_PATH}' 不存在。請在 main.py 中設定正確的路徑。")
    # exit() # 在實際運行時，如果權重不存在應該退出

# 圖像截取設定
IMAGE_OUTPUT_DIR = "live_captured_images"

# 輸送帶控制設定 (!!!需要您修改!!!)
CONVEYOR_CONTROL_TYPE = "custom"  # 'serial', 'gpio', or 'custom'
CONVEYOR_SERIAL_PORT = None       # 例如 'COM3' or '/dev/ttyUSB0' (if serial)
CONVEYOR_GPIO_PINS = None         # 例如 {'forward': 17, 'enable': 27, 'sensor': 22} (if gpio)
CONVEYOR_PICKUP_SENSOR_PIN = None # GPIO pin for pickup sensor (if gpio and used)

# 機械手臂控制設定 (!!!需要您修改!!!)
# 順序: [base, shoulder, elbow, wrist_pitch, wrist_roll, special_joint]
ARM_JOINT_PINS = [17, 18, 27, 22, 23, 24] # 示例腳位, 請替換
ARM_GRIPPER_PIN = 25                      # 示例腳位, 請替換
ARM_PWM_LIB_TYPE = "custom"               # 'jetson_gpio', 'rpi_gpio', or 'custom'

# 產品類別到分類區域的映射 (!!!需要您定義!!!)
# 假設 Yolov12 輸出的 'label' 是字符串 'class_A', 'class_B' 等
# 或者數字索引 '0', '1' 等，您需要根據實際情況調整
PRODUCT_TO_ZONE_MAP = {
    "class_A": 1,  # 產品 "class_A" 放到區域 1
    "class_B": 2,  # 產品 "class_B" 放到區域 2
    "class_C": 3,  # 產品 "class_C" 放到區域 3
    "class_D": 4,  # 產品 "class_D" 放到區域 4
    # 如果您的 YOLO 輸出是數字標籤，例如 '0', '1', ...
    # "0": 1,
    # "1": 2,
}
# 如果沒有偵測到物件或是不認識的物件，可以定義一個預設區域或動作
DEFAULT_ZONE_FOR_UNKNOWN = None # 例如 0, 或其他處理方式

# 等待產品到達拍攝區的邏輯 (簡化)
# 在實際應用中，這裡可能是一個感測器觸發
def wait_for_product_arrival(method="timer", duration=5):
    """
    等待產品到達。
    'timer': 固定延遲。
    'manual': 等待使用者輸入。
    未來可以擴展為 'sensor'。
    """
    if method == "timer":
        print(f"等待產品到達 (延時 {duration} 秒)...")
        time.sleep(duration)
        return True
    elif method == "manual":
        input("請將產品放置到拍攝位置，然後按 Enter 繼續...")
        return True
    # elif method == "sensor":
    #     # 實現感測器等待邏輯
    #     pass
    return False


def main_process():
    print("--- 自動化分類系統啟動 ---")

    # 1. 初始化各模組
    print("\n[1. 初始化模組]")
    yolo_detector = None # 在 try 外部先定義，以便 finally 中可以檢查
    conveyor = None
    robot_arm = None
    try:
        # 初始化 Yolov12 偵測器
        print("  正在初始化 YOLOv12 偵測器...")
        yolo_detector = YOLOv12Detector(weights_path=YOLO_WEIGHTS_PATH, device='cpu') # 或 'cuda'
        if yolo_detector.model is None and os.path.exists(YOLO_WEIGHTS_PATH) : # 增加了對權重檔案是否存在的檢查
            print("  YOLOv12 模型未能載入，即使權重檔案存在。請檢查 yolo_inference.py 中的載入邏輯。")
            return # 嚴重錯誤，無法繼續
        elif not os.path.exists(YOLO_WEIGHTS_PATH):
             print(f"  YOLOv12 權重檔案 {YOLO_WEIGHTS_PATH} 未找到，YOLO 功能將受限。")
             # 根據需要決定是否退出
        else:
            print("  YOLOv12 偵測器初始化完成。")

        # 初始化輸送帶控制器
        print("  正在初始化輸送帶控制器...")
        conveyor = ConveyorControl(port=CONVEYOR_SERIAL_PORT,
                                  control_pins=CONVEYOR_GPIO_PINS,
                                  control_type=CONVEYOR_CONTROL_TYPE)
        if not conveyor.connect(): # 嘗試連接
            print("  錯誤：無法連接到輸送帶控制器。請檢查設定。")
            # return # 可以選擇退出或繼續（如果某些部分不需要輸送帶）
        else:
            print("  輸送帶控制器初始化並連接完成。")

        # 初始化機械手臂控制器
        print("  正在初始化機械手臂控制器...")
        robot_arm = RobotArmControl(joint_pins=ARM_JOINT_PINS,
                                    gripper_pin=ARM_GRIPPER_PIN,
                                    pwm_lib_type=ARM_PWM_LIB_TYPE)
        # robot_arm.move_to_named_position("home") # 初始化後移動到 home
        print("  機械手臂控制器初始化完成 (示意移動到 home)。")

    except Exception as e:
        print(f"初始化過程中發生嚴重錯誤: {e}")
        # 即使初始化失敗，也嘗試清理已部分初始化的物件
        if conveyor and hasattr(conveyor, 'is_connected') and conveyor.is_connected:
            conveyor.disconnect()
        if robot_arm:
            robot_arm.cleanup()
        return

    # --- 主處理循環 ---
    try:
        run_count = 0
        max_runs = 3 # 示例：處理3個產品後結束
        while run_count < max_runs:
            run_count += 1
            print(f"\n--- 開始處理第 {run_count} 個產品 ---")

            # 2. 等待產品到達拍攝區
            print("\n[2. 等待產品]")
            if not wait_for_product_arrival(method="manual"): # 改為 "timer" 進行自動延時
                print("未能等到產品，結束本次處理。")
                continue

            # 3. 截取圖片
            print("\n[3. 截取圖片]")
            captured_image_path = capture_image(output_dir=IMAGE_OUTPUT_DIR, filename_prefix=f"product_{run_count}")
            if not captured_image_path:
                print("  錯誤：截圖失敗。跳過此產品。")
                continue
            print(f"  圖片已保存到: {captured_image_path}")

            # 4. Yolov12 推論
            print("\n[4. YOLOv12 推論]")
            if yolo_detector and hasattr(yolo_detector, 'model') and yolo_detector.model: # 確保 yolo_detector 和其模型已初始化
                detections = yolo_detector.detect(captured_image_path)
                if detections:
                    # 假設我們只關心第一個偵測到的高信心度物件
                    # 您可能需要更複雜的邏輯來選擇目標物件
                    best_detection = detections[0] # 簡化：取第一個
                    product_label = best_detection['label']
                    confidence = best_detection['confidence']
                    print(f"  偵測到產品: {product_label} (信心度: {confidence:.2f})")

                    # 5. 決策：根據產品類別確定目標區域
                    target_zone = PRODUCT_TO_ZONE_MAP.get(product_label, DEFAULT_ZONE_FOR_UNKNOWN)

                    if target_zone is not None:
                        print(f"  產品 '{product_label}' 將被放置到區域 {target_zone}。")

                        # 6. 輸送帶移動產品到夾取點
                        print("\n[6. 輸送帶移動]")
                        if conveyor and hasattr(conveyor, 'is_connected') and conveyor.is_connected:
                            if conveyor.move_to_pickup_point(sensor_pin=CONVEYOR_PICKUP_SENSOR_PIN):
                                print("  產品已到達機械手臂夾取點。")

                                # 7. 機械手臂夾取
                                print("\n[7. 機械手臂夾取]")
                                if robot_arm:
                                    # robot_arm.move_to_named_position("home") # 確保從 home 開始或夾取預備
                                    # time.sleep(0.5)
                                    if robot_arm.pickup_object():
                                        print("  機械手臂已成功夾取產品。")

                                        # 8. 機械手臂放置
                                        print("\n[8. 機械手臂放置]")
                                        if robot_arm.place_object_in_zone(target_zone):
                                            print(f"  產品已成功放置到區域 {target_zone}。")
                                        else:
                                            print(f"  錯誤：放置產品到區域 {target_zone} 失敗。")
                                            # 可能需要錯誤處理，例如將產品放到廢棄區
                                    else:
                                        print("  錯誤：機械手臂夾取產品失敗。")
                                else:
                                    print("  錯誤：機械手臂未初始化。")
                            else:
                                print("  錯誤：輸送帶未能將產品移動到夾取點。")
                        else:
                            print("  錯誤：輸送帶未連接或未初始化。")
                    else:
                        print(f"  未知的產品類別 '{product_label}' 或未定義處理方式。產品將被忽略。")
                else:
                    print("  未偵測到任何物件。")
            else:
                print("  YOLOv12 偵測器未初始化或模型未載入，跳過推論。")

            # 清理本次截圖 (可選)
            # if os.path.exists(captured_image_path):
            #     os.remove(captured_image_path)
            #     print(f"  已刪除截圖: {captured_image_path}")

            if run_count < max_runs:
                print(f"\n準備處理下一個產品...")
                time.sleep(2) # 短暫延遲

        print(f"\n--- 已完成處理 {max_runs} 個產品 ---")

    except KeyboardInterrupt:
        print("\n偵測到手動中斷 (Ctrl+C)。正在停止程式...")
    except Exception as e:
        print(f"主處理循環中發生錯誤: {e}")
    finally:
        # 9. 清理資源
        print("\n[9. 清理資源]")
        if conveyor and hasattr(conveyor, 'is_connected') and conveyor.is_connected: # 檢查 conveyor 是否已定義且有 is_connected 屬性
            print("  正在停止並斷開輸送帶...")
            conveyor.stop()
            conveyor.disconnect()
        if robot_arm: # 檢查 robot_arm 是否已定義
            print("  正在清理機械手臂...")
            # robot_arm.move_to_named_position("home") # 確保手臂在安全位置
            robot_arm.cleanup()
        print("--- 自動化分類系統關閉 ---")

if __name__ == '__main__':
    # 創建圖片保存目錄 (如果不存在)
    if not os.path.exists(IMAGE_OUTPUT_DIR):
        os.makedirs(IMAGE_OUTPUT_DIR)

    main_process()
