# robot_arm_control.py
import time

# 根據您的 Jetson Orin Nano 環境，您可能需要使用特定的 GPIO 或 PWM 函式庫
# 例如:
# 1. RPi.GPIO (如果 Jetson Orin Nano 上的 GPIO 與 Raspberry Pi 兼容且您選擇使用此庫)
#    安裝: pip install RPi.GPIO
#    import RPi.GPIO as GPIO
# 2. Jetson.GPIO (NVIDIA 官方提供的函式庫)
#    安裝: pip install Jetson.GPIO
#    import Jetson.GPIO as GPIO
# 3. 使用 sysfs 直接控制 PWM (較底層)
# 4. 使用 pigpio 庫 (如果移植且配置正確)

# --- PWM 配置常量 ---
PWM_FREQUENCY = 50  # Hz, 標準伺服馬達頻率
# MG996R 脈衝寬度範圍 (ms) - 這些值可能需要為您的具體舵機進行校準
# 0.5ms ~ -90度, 1.5ms ~ 0度, 2.5ms ~ +90度 (近似值)
# 換算成占空比 (Duty Cycle) for RPi.GPIO: (pulse_ms / 20ms) * 100
# pulse_ms = angle_to_ms(angle)
MIN_PULSE_MS = 0.6  # 最小脈衝寬度 (ms) 對應 -90 度左右
MID_PULSE_MS = 1.5  # 中間脈衝寬度 (ms) 對應 0 度左右
MAX_PULSE_MS = 2.4  # 最大脈衝寬度 (ms) 對應 +90 度左右

# 轉換角度到占空比 (一個簡化的線性映射)
# 實際中，您可能需要為每個舵機校準這個函數
def angle_to_duty_cycle(angle_deg, min_angle=-90, max_angle=90,
                        min_pulse_ms=MIN_PULSE_MS, max_pulse_ms=MAX_PULSE_MS,
                        pwm_freq=PWM_FREQUENCY):
    """
    將角度 (-90 to +90) 轉換為 PWM 占空比 (0-100)。
    注意：這是一個線性近似，實際舵機響應可能非線性，需要校準。
    """
    if not (min_angle <= angle_deg <= max_angle):
        print(f"警告：角度 {angle_deg} 超出範圍 [{min_angle}, {max_angle}]。將其限制在範圍內。")
        angle_deg = max(min_angle, min(angle_deg, max_angle))

    # 將角度映射到脈衝寬度 (ms)
    pulse_ms = min_pulse_ms + (angle_deg - min_angle) * (max_pulse_ms - min_pulse_ms) / (max_angle - min_angle)

    # 將脈衝寬度 (ms) 轉換為占空比 (%)
    period_ms = 1000.0 / pwm_freq
    duty_cycle = (pulse_ms / period_ms) * 100.0
    return duty_cycle


class RobotArmControl:
    def __init__(self, joint_pins, gripper_pin, pwm_lib_type="jetson_gpio"):
        """
        初始化機械手臂控制器。

        Args:
            joint_pins (list of int): 六個關節伺服馬達的 PWM 控制腳位 (BCM 編號或硬體 PWM 通道號)。
                                      順序應與您的機械手臂關節定義一致。
                                      例如: [base_pin, shoulder_pin, elbow_pin, wrist_pitch_pin, wrist_roll_pin, special_joint_pin]
            gripper_pin (int): 夾爪伺服馬達的 PWM 控制腳位。
            pwm_lib_type (str): 使用的 PWM/GPIO 函式庫類型 ('jetson_gpio', 'rpi_gpio', 'custom')。
        """
        if len(joint_pins) != 6:
            raise ValueError("joint_pins 列表必須包含 6 個腳位號碼。")

        self.joint_pins = joint_pins
        self.gripper_pin = gripper_pin
        self.pwm_lib_type = pwm_lib_type.lower()
        self.pwm_objects = {}  # 存放每個腳位的 PWM 物件 {pin: pwm_instance}

        # 關節活動範圍 (角度) - !!! 您必須為您的機械手臂校準這些值 !!!
        # 格式: (min_angle, max_angle)
        self.joint_limits = [
            (-90, 90),  # 關節 0 (例如 基座)
            (-90, 90),  # 關節 1 (例如 肩部)
            (-90, 90),  # 關節 2 (例如 肘部)
            (-90, 90),  # 關節 3 (例如 腕部俯仰)
            (-90, 90),  # 關節 4 (例如 腕部旋轉)
            (-90, 90),  # 關節 5 (第六個自由度)
        ]
        # 夾爪開合角度 - !!! 您必須校準這些值 !!!
        self.gripper_open_angle = -30  # 假設夾爪張開的角度
        self.gripper_closed_angle = 30 # 假設夾爪閉合的角度

        self._initialize_pwm()

        # 預定義位置 (每個關節的角度列表) - !!! 示教或計算得到 !!!
        self.predefined_positions = {
            "home": [0, 0, 0, 0, 0, 0], # 初始/安全位置
            "pickup_approach": [-10, -20, 30, 0, 0, 0], # 夾取點預備位置
            "pickup": [0, -30, 45, 0, 0, 0],      # 精確夾取位置
            "zone1_drop": [30, -20, 30, 0, 0, 0], # 分類區域1的釋放位置
            "zone2_drop": [60, -20, 30, 0, 0, 0], # 分類區域2的釋放位置
            "zone3_drop": [-30, -20, 30, 0, 0, 0],# 分類區域3的釋放位置
            "zone4_drop": [-60, -20, 30, 0, 0, 0],# 分類區域4的釋放位置
        }
        print("機械手臂控制器已初始化。")

    def _initialize_pwm(self):
        """(私有) 初始化 PWM 腳位。"""
        print(f"使用 {self.pwm_lib_type} 初始化 PWM...")
        all_pins = self.joint_pins + [self.gripper_pin]

        if self.pwm_lib_type == "jetson_gpio":
            try:
                # import Jetson.GPIO as GPIO
                # GPIO.setmode(GPIO.BCM) # 或 BOARD，取決於您的腳位編號方式
                # for pin in all_pins:
                #     GPIO.setup(pin, GPIO.OUT)
                #     pwm = GPIO.PWM(pin, PWM_FREQUENCY)
                #     pwm.start(0) # 初始占空比為 0 (通常舵機會保持不動或到一個極限)
                #     self.pwm_objects[pin] = pwm
                # print("Jetson.GPIO PWM 腳位已成功設定。")
                print("示意：嘗試使用 Jetson.GPIO 設定 PWM。")
                print("您需要取消註解並安裝 'Jetson.GPIO'，並實現實際的設定邏輯。")
                # 為了框架開發，假設成功
                for pin in all_pins: self.pwm_objects[pin] = "dummy_pwm_jetson"
            except Exception as e:
                print(f"錯誤：初始化 Jetson.GPIO PWM 失敗。{e}")
                raise

        elif self.pwm_lib_type == "rpi_gpio":
            try:
                # import RPi.GPIO as GPIO
                # GPIO.setmode(GPIO.BCM)
                # for pin in all_pins:
                #     GPIO.setup(pin, GPIO.OUT)
                #     pwm = GPIO.PWM(pin, PWM_FREQUENCY)
                #     pwm.start(angle_to_duty_cycle(0)) # 啟動並設置到中間位置 (0度)
                #     self.pwm_objects[pin] = pwm
                # print("RPi.GPIO PWM 腳位已成功設定。")
                print("示意：嘗試使用 RPi.GPIO 設定 PWM。")
                print("您需要取消註解並安裝 'RPi.GPIO'，並實現實際的設定邏輯。")
                for pin in all_pins: self.pwm_objects[pin] = "dummy_pwm_rpi"
            except Exception as e:
                print(f"錯誤：初始化 RPi.GPIO PWM 失敗。{e}")
                raise
        elif self.pwm_lib_type == "custom":
            print("使用自訂 PWM 初始化邏輯。請確保已在外部或子類別中設定。")
            # 您可能需要在此處調用一個自訂的設定函數
            # for pin in all_pins: self.pwm_objects[pin] = setup_my_custom_pwm(pin)
            for pin in all_pins: self.pwm_objects[pin] = "dummy_pwm_custom"
        else:
            raise ValueError(f"不支援的 pwm_lib_type: {self.pwm_lib_type}")

        # 初始時將所有關節移動到 "home" 位置
        # self.move_to_named_position("home", speed=0.05) # 較慢的初始移動
        print("示意：手臂初始化後應移動到 'home' 位置。")


    def set_joint_angle(self, joint_index, angle_deg, speed=0.02):
        """
        設定單個關節的角度。

        Args:
            joint_index (int): 關節的索引 (0-5)。
            angle_deg (float): 目標角度 (度)。
            speed (float): 舵機轉動的延遲時間，模擬速度，值越小越快 (秒/度，粗略估計)。
                           實際速度取決於舵機本身。設為0則瞬時到達。
        """
        if not (0 <= joint_index < len(self.joint_pins)):
            print(f"錯誤：無效的關節索引 {joint_index}。")
            return

        pin = self.joint_pins[joint_index]
        min_a, max_a = self.joint_limits[joint_index]
        angle_deg = max(min_a, min(angle_deg, max_a)) # 限制在活動範圍內

        duty_cycle = angle_to_duty_cycle(angle_deg, min_a, max_a)
        current_duty_cycle = 0 # 理想情況下應能讀取當前占空比或角度

        print(f"設定關節 {joint_index} (腳位 {pin}) 到角度 {angle_deg:.1f}° (占空比 {duty_cycle:.2f}%)...")

        if self.pwm_lib_type in ["jetson_gpio", "rpi_gpio"]:
            pwm = self.pwm_objects.get(pin)
            if pwm:
                # pwm.ChangeDutyCycle(duty_cycle)
                # 如果需要模擬平滑移動 (非常粗略的模擬)
                # if speed > 0 and hasattr(pwm, 'start_angle_for_pin'): # 假設我們能獲取當前角度
                #     start_angle = pwm.start_angle_for_pin[pin]
                #     delta_angle = abs(angle_deg - start_angle)
                #     num_steps = int(delta_angle / 1) # 每1度一步
                #     for step_angle in np.linspace(start_angle, angle_deg, num_steps):
                #         step_duty = angle_to_duty_cycle(step_angle, min_a, max_a)
                #         pwm.ChangeDutyCycle(step_duty)
                #         time.sleep(speed) # * (delta_angle / num_steps)
                # else:
                # pwm.ChangeDutyCycle(duty_cycle)
                print(f"示意：腳位 {pin} 的 PWM 占空比改為 {duty_cycle:.2f}。")
                if speed > 0: time.sleep(0.5) # 示意延遲
            else:
                print(f"錯誤：腳位 {pin} 的 PWM 物件未找到。")
        elif self.pwm_lib_type == "custom":
            # self.custom_set_pwm_duty_cycle(pin, duty_cycle)
            print(f"示意：自訂 PWM 控制腳位 {pin} 的占空比為 {duty_cycle:.2f}。")
            if speed > 0: time.sleep(0.5) # 示意延遲


    def set_all_joint_angles(self, angles_deg_list, speed=0.02):
        """
        同時設定所有六個關節的角度。

        Args:
            angles_deg_list (list of float): 六個關節的目標角度列表。
            speed (float): 每個舵機的轉動延遲時間 (秒/度，粗略估計)。
        """
        if len(angles_deg_list) != len(self.joint_pins):
            print("錯誤：角度列表的長度必須與關節數量一致。")
            return
        print(f"設定所有關節角度為: {angles_deg_list}...")
        for i, angle_deg in enumerate(angles_deg_list):
            self.set_joint_angle(i, angle_deg, speed=speed if i == len(angles_deg_list) -1 else 0.001) # 最后一个关节可以慢一点，其他的快速设置
        # 可以增加一個整體的延遲來確保所有舵機都到達位置
        # max_angle_change = 0
        # for i in range(len(angles_deg_list)):
        #     # 假設能獲取當前角度
        #     # current_angle = self.get_joint_angle(i) # 需要實現 get_joint_angle
        #     # max_angle_change = max(max_angle_change, abs(angles_deg_list[i] - current_angle))
        #     pass # 示意
        # time.sleep(max_angle_change * speed if speed > 0 else 0.1)
        if speed > 0: time.sleep(1.0) # 示意整體延遲
        print("所有關節角度設定完成 (示意)。")


    def open_gripper(self, speed=0.02):
        """張開夾爪。"""
        print("指令：張開夾爪。")
        duty_cycle = angle_to_duty_cycle(self.gripper_open_angle)
        if self.pwm_lib_type in ["jetson_gpio", "rpi_gpio"]:
            pwm = self.pwm_objects.get(self.gripper_pin)
            if pwm:
                # pwm.ChangeDutyCycle(duty_cycle)
                print(f"示意：夾爪 (腳位 {self.gripper_pin}) PWM 占空比改為 {duty_cycle:.2f} (張開)。")
                if speed > 0: time.sleep(0.5) # 夾爪動作延遲
            else:
                print(f"錯誤：夾爪腳位 {self.gripper_pin} 的 PWM 物件未找到。")
        elif self.pwm_lib_type == "custom":
            # self.custom_set_pwm_duty_cycle(self.gripper_pin, duty_cycle)
            print(f"示意：自訂 PWM 控制夾爪腳位 {self.gripper_pin} 的占空比為 {duty_cycle:.2f} (張開)。")
            if speed > 0: time.sleep(0.5)


    def close_gripper(self, speed=0.02):
        """閉合夾爪。"""
        print("指令：閉合夾爪。")
        duty_cycle = angle_to_duty_cycle(self.gripper_closed_angle)
        if self.pwm_lib_type in ["jetson_gpio", "rpi_gpio"]:
            pwm = self.pwm_objects.get(self.gripper_pin)
            if pwm:
                # pwm.ChangeDutyCycle(duty_cycle)
                print(f"示意：夾爪 (腳位 {self.gripper_pin}) PWM 占空比改為 {duty_cycle:.2f} (閉合)。")
                if speed > 0: time.sleep(0.5) # 夾爪動作延遲
            else:
                print(f"錯誤：夾爪腳位 {self.gripper_pin} 的 PWM 物件未找到。")
        elif self.pwm_lib_type == "custom":
            # self.custom_set_pwm_duty_cycle(self.gripper_pin, duty_cycle)
            print(f"示意：自訂 PWM 控制夾爪腳位 {self.gripper_pin} 的占空比為 {duty_cycle:.2f} (閉合)。")
            if speed > 0: time.sleep(0.5)

    def move_to_named_position(self, position_name, speed=0.02):
        """
        將機械手臂移動到預定義的命名位置。

        Args:
            position_name (str): 預定義位置的名稱 (例如 "home", "pickup")。
            speed (float): 舵機轉動速度。
        """
        if position_name in self.predefined_positions:
            angles = self.predefined_positions[position_name]
            print(f"移動到預定義位置 '{position_name}' (角度: {angles})...")
            self.set_all_joint_angles(angles, speed=speed)
        else:
            print(f"錯誤：未知的預定義位置 '{position_name}'。")

    def pickup_object(self, approach_offset_angles=None, pickup_angles=None):
        """
        執行夾取物件的序列動作。
        1. 移動到夾取點的預備位置 (上方)
        2. 張開夾爪
        3. 向下移動到精確夾取點
        4. 閉合夾爪
        5. 向上提起物件

        Args:
            approach_offset_angles (list, optional): 相對於 pickup_angles 的接近點偏移角度。
                                                   如果為 None，則使用 "pickup_approach" 預定義位置。
            pickup_angles (list, optional): 精確的夾取點關節角度。
                                          如果為 None，則使用 "pickup" 預定義位置。
        """
        print("開始夾取物件序列...")

        # 1. 移動到夾取點的預備位置
        if approach_offset_angles:
            self.set_all_joint_angles(approach_offset_angles, speed=0.03)
        else:
            self.move_to_named_position("pickup_approach", speed=0.03)
        time.sleep(0.5) # 等待穩定

        # 2. 張開夾爪
        self.open_gripper()
        time.sleep(0.5)

        # 3. 向下移動到精確夾取點
        if pickup_angles:
            self.set_all_joint_angles(pickup_angles, speed=0.04) # 較慢速精確移動
        else:
            self.move_to_named_position("pickup", speed=0.04)
        time.sleep(0.5)

        # 4. 閉合夾爪
        self.close_gripper()
        time.sleep(0.7) # 等待夾爪夾緊

        # 5. 向上提起物件 (回到預備位置或稍高一點)
        print("向上提起物件...")
        if approach_offset_angles:
            # 也可以定義一個 "post_pickup_lift" 位置
            lifted_angles = list(approach_offset_angles) # 複製
            # 假設關節2是控制高度的主要關節之一，稍微抬高一點
            # lifted_angles[2] = max(self.joint_limits[2][0], lifted_angles[2] - 15)
            self.set_all_joint_angles(lifted_angles, speed=0.03)
        else:
            self.move_to_named_position("pickup_approach", speed=0.03) # 回到預備位置

        print("夾取物件序列完成。")
        return True # 假設成功

    def place_object_in_zone(self, zone_number):
        """
        將夾取的物件放置到指定的分類區域。

        Args:
            zone_number (int): 分類區域的編號 (1-4)。
        """
        zone_name = f"zone{zone_number}_drop"
        if zone_name not in self.predefined_positions:
            print(f"錯誤：無效的分類區域編號 {zone_number}。")
            return False

        print(f"開始將物件放置到分類區域 {zone_number}...")
        # 1. 移動到該區域的釋放點上方 (可以增加一個 approach_zoneX_drop 位置)
        self.move_to_named_position(zone_name, speed=0.02)
        time.sleep(0.5)

        # 2. 張開夾爪釋放物件
        self.open_gripper()
        time.sleep(0.7) # 等待物件落下

        # 3. 手臂移回安全位置 (例如 home)
        self.move_to_named_position("home", speed=0.02)
        print(f"物件已放置到分類區域 {zone_number} 並返回 Home。")
        return True

    def cleanup(self):
        """清理 PWM 和 GPIO 設定。"""
        print("正在清理機械手臂 PWM/GPIO 設定...")
        if self.pwm_lib_type in ["jetson_gpio", "rpi_gpio"]:
            for pin, pwm in self.pwm_objects.items():
                if hasattr(pwm, 'stop'): # RPi.GPIO 和 Jetson.GPIO 都有 stop()
                    # pwm.stop()
                    print(f"示意：停止腳位 {pin} 的 PWM。")
            if self.pwm_lib_type == "jetson_gpio":
                # import Jetson.GPIO as GPIO
                # GPIO.cleanup()
                print("示意：執行 Jetson.GPIO.cleanup()")
                pass
            elif self.pwm_lib_type == "rpi_gpio":
                # import RPi.GPIO as GPIO
                # GPIO.cleanup()
                print("示意：執行 RPi.GPIO.cleanup()")
                pass
        elif self.pwm_lib_type == "custom":
            # self.custom_cleanup_pwm()
            print("示意：執行自訂 PWM 清理邏輯。")
        print("機械手臂清理完成。")

    def __del__(self):
        """物件銷毀時自動清理。"""
        self.cleanup()


if __name__ == '__main__':
    print("--- 機械手臂控制框架測試 ---")

    # !!! 您需要根據您的硬體配置修改以下參數 !!!
    # 假設的 Jetson Orin Nano GPIO (BCM 編號) 或 PWM 通道號
    # 順序: [base, shoulder, elbow, wrist_pitch, wrist_roll, special_joint]
    example_joint_pins = [17, 18, 27, 22, 23, 24] # 請替換為您的實際腳位
    example_gripper_pin = 25                     # 請替換為您的實際腳位

    # 選擇 PWM 函式庫類型: 'jetson_gpio', 'rpi_gpio', 或 'custom'
    # 由於我們可能不在 Jetson/RPi 環境中直接執行此腳本進行完整測試，
    # 這裡使用 'custom' 類型，它只會印出訊息，不會嘗試實際控制硬體。
    # 當您在 Jetson 上部署時，應改為 'jetson_gpio' 並確保相關函式庫已安裝且腳位正確。
    pwm_library_to_use = "custom" # 改為 "jetson_gpio" 在 Jetson 上

    print(f"將使用 {pwm_library_to_use} 進行示意控制。")

    try:
        arm = RobotArmControl(joint_pins=example_joint_pins,
                              gripper_pin=example_gripper_pin,
                              pwm_lib_type=pwm_library_to_use)

        # 測試移動到 Home 位置
        arm.move_to_named_position("home", speed=0.03)
        time.sleep(1)

        # 測試夾爪
        print("\n測試夾爪...")
        arm.open_gripper()
        time.sleep(0.5)
        arm.close_gripper()
        time.sleep(0.5)

        # 測試單關節移動 (關節0, 30度)
        print("\n測試單關節移動...")
        arm.set_joint_angle(0, 30, speed=0.02)
        time.sleep(1)
        arm.set_joint_angle(0, -30, speed=0.02)
        time.sleep(1)
        arm.set_joint_angle(0, 0, speed=0.02) # 回到0度
        time.sleep(1)


        # --- 模擬一個完整的夾取和放置流程 ---
        print("\n--- 開始模擬夾取與放置流程 ---")
        # 1. 移動到 Home
        arm.move_to_named_position("home")
        time.sleep(0.5)

        # 2. 執行夾取 (假設物件在預定義的 pickup 位置)
        print("\n執行夾取物件...")
        if arm.pickup_object():
            print("物件已夾取。")
            time.sleep(1)

            # 3. 將物件放置到分類區域 1
            print("\n將物件放置到區域 1...")
            arm.place_object_in_zone(1)
            time.sleep(1)

            # 假設又來了一個物件，再次夾取
            print("\n再次執行夾取物件...")
            arm.move_to_named_position("home") # 先回 Home 或夾取預備
            if arm.pickup_object():
                print("第二個物件已夾取。")
                time.sleep(1)
                # 4. 將物件放置到分類區域 3
                print("\n將物件放置到區域 3...")
                arm.place_object_in_zone(3)
                time.sleep(1)

        arm.move_to_named_position("home") # 結束後回到 Home

    except Exception as e:
        print(f"測試過程中發生錯誤: {e}")
    finally:
        if 'arm' in locals() and arm is not None:
            arm.cleanup() # 確保清理

    print("\n--- 機械手臂控制框架測試完成 ---")
