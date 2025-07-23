import time
import numpy as np
from .base import HardwareController

class WindowsController(HardwareController):
    """
    Simulated hardware controller for Windows development.
    This class mimics the hardware's behavior by printing to the console
    and returning simulated data.
    """

    def __init__(self, config):
        """
        Initializes the simulated controller.
        """
        print("---")
        print("Initializing [WindowsController] in SIMULATION mode.")
        self.config = config
        self._is_camera_available = True
        self._sensor_triggered = False
        print("---")


    def capture_image(self):
        """
        Simulates capturing an image.
        Returns a placeholder black image.
        """
        print("[SIM] Capturing image...")
        # Create a black image as a placeholder
        frame = np.zeros((self.config.FRAME_HEIGHT, self.config.FRAME_WIDTH, 3), dtype=np.uint8)
        # Add text to indicate it's a simulated feed
        cv2.putText(frame, "Simulated Camera Feed", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        return frame

    def move_conveyor(self, distance, speed):
        """
        Simulates moving the conveyor belt.
        """
        print(f"[SIM] Moving conveyor forward by {distance} units at speed {speed}%.")
        time.sleep(1) # Simulate time taken for movement
        print("[SIM] Conveyor movement complete.")

    def stop_conveyor(self):
        """
        Simulates stopping the conveyor belt.
        """
        print("[SIM] Stopping conveyor belt.")

    def move_arm_to_position(self, position_name):
        """
        Simulates moving the robotic arm to a predefined position.
        """
        print(f"[SIM] Moving robotic arm to position: '{position_name}'.")
        # Simulate movement time
        time.sleep(1.5)
        print(f"[SIM] Arm reached '{position_name}'.")

    def read_sensor(self):
        """
        Simulates reading the photoelectric sensor.
        Alternates between True and False to allow the main loop to proceed.
        """
        # This simple logic simulates an object appearing and then disappearing
        self._sensor_triggered = not self._sensor_triggered
        print(f"[SIM] Photoelectric sensor triggered: {self._sensor_triggered}")
        return self._sensor_triggered

    def cleanup(self):
        """
        Simulates cleaning up resources.
        """
        print("[SIM] Cleaning up simulated hardware resources.")
        print("---")

# This allows running a simple test of the controller
if __name__ == '__main__':
    import config
    # Create a mock config for testing
    class MockConfig:
        FRAME_HEIGHT = 480
        FRAME_WIDTH = 640

    controller = WindowsController(MockConfig())
    controller.read_sensor()
    img = controller.capture_image()
    controller.move_conveyor(10, 80)
    controller.move_arm_to_position('pickup')
    controller.move_arm_to_position('home')
    controller.cleanup()
