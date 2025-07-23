import os

# --- General Settings ---
# Get the absolute path of the project's root directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Camera Settings ---
CAMERA_INDEX = 0  # Default camera index, 0 is usually the built-in webcam
FRAME_WIDTH = 640
FRAME_HEIGHT = 480

# --- YOLO Model Settings ---
# Place your YOLOv12 model in the 'models' directory
MODEL_DIR = os.path.join(BASE_DIR, 'models')
MODEL_NAME = 'pcb_yolo12x_retry.pt'  # Your model file name
MODEL_PATH = os.path.join(MODEL_DIR, MODEL_NAME)

# --- Hardware Settings (for Jetson) ---
# GPIO pin for the photoelectric sensor
PHOTOELECTRIC_SENSOR_PIN = 17 # Example GPIO pin, please change to your actual pin

# Conveyor belt control pin
CONVEYOR_PIN = 27 # Example GPIO pin

# --- Servo Motor Settings (PCA9685) ---
# Channels for the 6-axis robotic arm
SERVO_CHANNELS = {
    'base': 0,
    'shoulder': 1,
    'elbow': 2,
    'wrist_roll': 3,
    'wrist_pitch': 4,
    'gripper': 5
}

# Servo motor angle limits (min_pulse, max_pulse) and (min_angle, max_angle)
# These values might need calibration for your specific servos (MG966R)
SERVO_PULSE_LIMITS = (500, 2500) # Pulse width in microseconds
SERVO_ANGLE_LIMITS = (0, 180)   # Angle in degrees
