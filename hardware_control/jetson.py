import time
import cv2
from .base import HardwareController

# Attempt to import Jetson-specific libraries
try:
    import Jetson.GPIO as GPIO
    import board
    import busio
    from adafruit_pca9685 import PCA9685
    from adafruit_motor import servo
    GPIO_AVAILABLE = True
except ImportError:
    print("Warning: Jetson GPIO libraries not found. JetsonController will not function.")
    GPIO_AVAILABLE = False

class JetsonController(HardwareController):
    """
    Hardware controller for NVIDIA Jetson platforms.
    This class interfaces with the actual hardware like GPIO, I2C, and cameras.
    """

    def __init__(self, config):
        """
        Initializes the Jetson hardware controller.
        """
        super().__init__(config)
        print("---")
        print("Initializing [JetsonController]...")
        self.config = config
        self.pca = None
        self.servos = {}
        self.camera = None

        if not GPIO_AVAILABLE:
            raise RuntimeError("Cannot instantiate JetsonController: GPIO libraries are missing.")

        self._initialize_gpio()
        self._initialize_pca()
        self._initialize_camera()
        print("---")

    def _initialize_gpio(self):
        """Initializes GPIO pins."""
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            # Setup for conveyor belt, assuming a simple relay or motor driver
            GPIO.setup(self.config.CONVEYOR_PIN, GPIO.OUT, initial=GPIO.LOW)
            # Setup for the photoelectric sensor
            GPIO.setup(self.config.PHOTOELECTRIC_SENSOR_PIN, GPIO.IN)
            print("GPIO pins initialized successfully.")
        except Exception as e:
            print(f"Error initializing GPIO: {e}")
            raise

    def _initialize_pca(self):
        """Initializes the PCA9685 servo driver."""
        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self.pca = PCA9685(i2c)
            self.pca.frequency = 50  # Set frequency to 50hz, standard for servos

            # Create servo objects for each channel defined in config
            for name, channel in self.config.SERVO_CHANNELS.items():
                self.servos[name] = servo.Servo(
                    self.pca.channels[channel],
                    min_pulse=self.config.SERVO_PULSE_LIMITS[0],
                    max_pulse=self.config.SERVO_PULSE_LIMITS[1]
                )
            print("PCA9685 and servos initialized successfully.")
        except Exception as e:
            print(f"Error initializing PCA9685: {e}")
            raise

    def _initialize_camera(self):
        """Initializes the USB camera."""
        try:
            self.camera = cv2.VideoCapture(self.config.CAMERA_INDEX)
            if not self.camera.isOpened():
                raise IOError("Cannot open camera")
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.FRAME_WIDTH)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.FRAME_HEIGHT)
            print(f"Camera at index {self.config.CAMERA_INDEX} initialized successfully.")
        except Exception as e:
            print(f"Error initializing camera: {e}")
            self.camera = None
            raise

    def capture_image(self):
        """Captures an image from the camera."""
        if self.camera and self.camera.isOpened():
            ret, frame = self.camera.read()
            if ret:
                return frame
        print("Error: Could not capture frame from camera.")
        return None

    def move_conveyor(self, distance, speed):
        """
        Moves the conveyor belt.
        For simplicity, this implementation just turns it on for a calculated duration.
        'distance' and 'speed' are used to calculate the duration.
        A more advanced implementation would use encoders.
        """
        if distance <= 0 or speed <= 0:
            return

        # Simple time-based movement: duration = distance / speed
        # This is a placeholder logic. You'll need to calibrate this.
        duration = distance / (speed * 0.1) # Arbitrary scaling factor

        print(f"Moving conveyor for {duration:.2f} seconds.")
        GPIO.output(self.config.CONVEYOR_PIN, GPIO.HIGH)
        time.sleep(duration)
        GPIO.output(self.config.CONVEYOR_PIN, GPIO.LOW)
        print("Conveyor movement complete.")

    def stop_conveyor(self):
        """Stops the conveyor belt immediately."""
        GPIO.output(self.config.CONVEYOR_PIN, GPIO.LOW)
        print("Conveyor stopped.")

    def move_arm_to_position(self, position_name):
        """
        Moves the robotic arm to a predefined position.
        This is a placeholder. You need to define the angles for each position.
        """
        # Example positions - these angles need to be calibrated
        positions = {
            'home': {'base': 90, 'shoulder': 150, 'elbow': 30, 'gripper': 90},
            'pickup': {'base': 90, 'shoulder': 100, 'elbow': 80, 'gripper': 90},
            'class1': {'base': 30, 'shoulder': 100, 'elbow': 80, 'gripper': 30},
            'class2': {'base': 150, 'shoulder': 100, 'elbow': 80, 'gripper': 30},
        }

        if position_name not in positions:
            print(f"Error: Position '{position_name}' not defined.")
            return

        target_angles = positions[position_name]
        print(f"Moving arm to position: '{position_name}' with angles {target_angles}")

        for name, angle in target_angles.items():
            if name in self.servos:
                self.servos[name].angle = angle
            time.sleep(0.1) # Small delay between servo movements

    def read_sensor(self):
        """Reads the state of the photoelectric sensor."""
        # Assuming the sensor is HIGH when an object is detected
        return GPIO.input(self.config.PHOTOELECTRIC_SENSOR_PIN) == GPIO.HIGH

    def cleanup(self):
        """Cleans up all hardware resources."""
        print("Cleaning up hardware resources...")
        if self.camera:
            self.camera.release()

        # Return arm to home position
        self.move_arm_to_position('home')
        time.sleep(1)

        if self.pca:
            self.pca.deinit()

        GPIO.cleanup()
        print("Cleanup complete.")
