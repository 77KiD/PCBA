import time

# --- Library Handling ---
# Attempt to import hardware-specific libraries, with a fallback for non-hardware environments.
try:
    import Jetson.GPIO as GPIO
    JETSON_GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    print("警告：無法匯入 Jetson.GPIO。GPIO 控制模式將在 '示意模式' 下運行。")
    JETSON_GPIO_AVAILABLE = False

try:
    import serial
    PYSERIAL_AVAILABLE = True
except ImportError:
    print("警告：無法匯入 pyserial。序列(serial)控制模式將在 '示意模式' 下運行。")
    PYSERIAL_AVAILABLE = False


class ConveyorControl:
    def __init__(self, port=None, baudrate=9600, control_pins=None, control_type="serial"):
        """
        Initializes the Conveyor Belt Controller.
        """
        # --- User Configuration ---
        self.port = port
        self.baudrate = baudrate
        self.control_pins = control_pins # e.g., {'forward': 17, 'enable': 27, 'sensor': 22}
        self.control_type = control_type.lower()

        self.is_connected = False
        self.ser = None  # Serial object
        self.is_dummy = False # Flag for simulation mode

        if self.control_type == "serial" and not PYSERIAL_AVAILABLE:
            print(f"錯誤：已選擇 'serial' 控制，但 'pyserial' 函式庫不可用。")
            self.is_dummy = True
        elif self.control_type == "gpio" and not JETSON_GPIO_AVAILABLE:
            print(f"錯誤：已選擇 'gpio' 控制，但 'Jetson.GPIO' 函式庫不可用。")
            self.is_dummy = True
        elif self.control_type not in ["serial", "gpio", "custom"]:
            raise ValueError(f"不支援的控制類型 '{self.control_type}'。請選擇 'serial', 'gpio', 或 'custom'。")

        print(f"輸送帶控制器已初始化 (類型: {self.control_type})。")

    def _connect_serial(self):
        """(Private) Connect to the serial port."""
        if self.is_dummy or self.port is None:
            print("示意模式：跳過序列埠連接。")
            self.is_connected = True # Assume success for simulation
            return True
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            self.is_connected = True
            print(f"已成功連接到序列埠 {self.port} (鮑率: {self.baudrate})。")
            return True
        except serial.SerialException as e:
            print(f"錯誤：無法連接到序列埠 {self.port}。{e}")
            self.is_connected = False
            return False

    def _disconnect_serial(self):
        """(Private) Disconnect the serial port."""
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.is_connected = False
        print("已斷開序列埠的連接。")

    def _setup_gpio(self):
        """(Private) Set up GPIO pins."""
        if self.is_dummy or self.control_pins is None:
            print("示意模式：跳過 GPIO 設定。")
            self.is_connected = True # Assume success for simulation
            return True
        try:
            GPIO.setmode(GPIO.BCM)
            # Setup output pins (motor control)
            for pin_name, pin_num in self.control_pins.items():
                if pin_name != 'sensor': # Don't set sensor pin as output
                    GPIO.setup(pin_num, GPIO.OUT)
                    GPIO.output(pin_num, GPIO.LOW) # Default to off
            # Setup input pin (sensor)
            if 'sensor' in self.control_pins:
                 # Use a pull-up resistor if the sensor is open-drain/open-collector (common)
                GPIO.setup(self.control_pins['sensor'], GPIO.IN, pull_up_down=GPIO.PUD_UP)

            self.is_connected = True
            print("GPIO 腳位已成功設定。")
            return True
        except Exception as e:
            print(f"錯誤：設定 GPIO 腳位失敗。{e}")
            self.is_connected = False
            return False

    def _cleanup_gpio(self):
        """(Private) Clean up GPIO settings."""
        if not self.is_dummy:
            GPIO.cleanup()
            print("GPIO 設定已清理。")

    def connect(self):
        """Connects to the conveyor controller based on the selected type."""
        if self.is_connected:
            print("控制器已經連接。")
            return True

        if self.control_type == "serial":
            return self._connect_serial()
        elif self.control_type == "gpio":
            return self._setup_gpio()
        elif self.control_type == "custom":
            print("自訂連接邏輯。假設連接成功。")
            self.is_connected = True
            return True
        return False

    def disconnect(self):
        """Disconnects from the conveyor controller."""
        if self.control_type == "serial":
            self._disconnect_serial()
        elif self.control_type == "gpio":
            # GPIO cleanup is usually called at the very end of the program
            self.is_connected = False
        elif self.control_type == "custom":
            print("自訂斷開邏輯。")
            self.is_connected = False
        print("輸送帶控制器已斷開。")

    def _send_command(self, command):
        """(Private) Sends a command to the controller."""
        if not self.is_connected:
            print("無法發送指令：控制器未連接。")
            return

        if self.is_dummy:
            print(f"示意指令: {command}")
            return

        if self.control_type == "serial":
            # Note: Ensure your command format (e.g., with '\n') matches the device's protocol.
            self.ser.write(f"{command}\n".encode('utf-8'))
        elif self.control_type == "gpio":
            # This logic assumes 'command' is a pin name like 'forward' or 'enable'
            # and the value is HIGH. A more complex system might take a dict.
            pin_to_activate = self.control_pins.get(command)
            if pin_to_activate:
                GPIO.output(pin_to_activate, GPIO.HIGH)
            # Also handle enable pin if present
            if 'enable' in self.control_pins:
                GPIO.output(self.control_pins['enable'], GPIO.HIGH)
        elif self.control_type == "custom":
            # Your custom logic here
            pass

    def start_forward(self):
        """Starts the conveyor moving forward."""
        print("指令：啟動輸送帶向前。")
        # --- User Action: Define your actual command/pin name ---
        command = "FORWARD" if self.control_type == "serial" else "forward"
        self._send_command(command)
        return True

    def stop(self):
        """Stops the conveyor."""
        print("指令：停止輸送帶。")
        if self.is_dummy:
            print("示意指令: STOP")
            return True

        if self.control_type == "serial":
            # --- User Action: Define your stop command ---
            self._send_command("STOP")
        elif self.control_type == "gpio":
            # Set all control pins to LOW to stop the motor
            for pin_name, pin_num in self.control_pins.items():
                if pin_name != 'sensor':
                    GPIO.output(pin_num, GPIO.LOW)
        elif self.control_type == "custom":
            # Your custom logic here
            pass
        return True

    def move_to_pickup_point(self, timeout=10):
        """
        Moves the product to the pickup point, using a sensor if available.
        """
        print("指令：將產品移動到夾取點。")
        if not self.start_forward():
            return False

        start_time = time.time()
        product_at_pickup = False

        # --- Sensor Logic ---
        print(f"等待產品到達夾取點 (超時: {timeout}s)...")
        while time.time() - start_time < timeout:
            if self.is_dummy:
                print("示意模式：等待 2 秒...")
                time.sleep(2)
                product_at_pickup = True
                break

            if self.control_type == "gpio":
                sensor_pin = self.control_pins.get('sensor')
                if sensor_pin:
                    # Assuming sensor reads LOW when triggered (active-low) due to PUD_UP.
                    # Change to GPIO.HIGH if your sensor is active-high.
                    if GPIO.input(sensor_pin) == GPIO.LOW:
                        product_at_pickup = True
                        break
                else:
                    print("警告：未配置感測器腳位，將使用定時移動。")
                    time.sleep(3) # Fallback to fixed delay
                    product_at_pickup = True
                    break

            elif self.control_type == "serial":
                # Assuming the controller sends a specific message e.g., "ARRIVED"
                if self.ser.in_waiting > 0:
                    response = self.ser.readline().decode('utf-8').strip()
                    if "ARRIVED" in response: # --- User Action: Define your arrival message ---
                        product_at_pickup = True
                        break

            else: # Custom or no sensor
                print("警告：無感測器邏輯，將使用定時移動。")
                time.sleep(3) # Fallback to fixed delay
                product_at_pickup = True
                break

            time.sleep(0.05) # Polling interval

        self.stop()

        if product_at_pickup:
            print("產品已到達夾取點。")
        else:
            print(f"錯誤：產品未能在 {timeout} 秒內到達夾取點。")

        return product_at_pickup

    def __del__(self):
        """Destructor to ensure resources are released."""
        self.disconnect()
        if self.control_type == "gpio" and not self.is_dummy:
            self._cleanup_gpio()


if __name__ == '__main__':
    print("--- 輸送帶控制框架測試 ---")

    # --- Test Case 1: Serial Control (Simulated) ---
    print("\n--- 測試序列控制 (示意) ---")
    # To run for real: conveyor_serial = ConveyorControl(port='COM3', control_type="serial")
    conveyor_serial = ConveyorControl(port='COM3', control_type="serial")
    if conveyor_serial.connect():
        conveyor_serial.start_forward()
        time.sleep(1)
        conveyor_serial.stop()
        time.sleep(0.5)
        conveyor_serial.move_to_pickup_point(timeout=5)
        conveyor_serial.disconnect()
    else:
        print("無法連接到序列輸送帶控制器。")

    # --- Test Case 2: GPIO Control (Simulated) ---
    print("\n--- 測試 GPIO 控制 (示意) ---")
    gpio_pins = {'forward': 17, 'enable': 27, 'sensor': 22}
    conveyor_gpio = ConveyorControl(control_pins=gpio_pins, control_type="gpio")
    if conveyor_gpio.connect():
        conveyor_gpio.start_forward()
        time.sleep(1)
        conveyor_gpio.stop()
        time.sleep(0.5)
        conveyor_gpio.move_to_pickup_point(timeout=5)
        conveyor_gpio.disconnect()
        # GPIO cleanup is handled in the destructor, but can be called manually if needed
        if JETSON_GPIO_AVAILABLE: GPIO.cleanup()
    else:
       print("無法初始化 GPIO 輸送帶控制器。")

    print("\n--- 輸送帶控制框架測試完成 ---")
