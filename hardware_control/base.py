from abc import ABC, abstractmethod

class HardwareController(ABC):
    """
    Abstract Base Class for hardware control.
    Defines the common interface for all hardware controllers.
    """

    @abstractmethod
    def __init__(self, config):
        """
        Initialize the hardware controller.
        'config' is a dictionary or object with hardware settings.
        """
        pass

    @abstractmethod
    def capture_image(self):
        """
        Capture an image from the camera.
        Returns a NumPy array representing the image.
        """
        pass

    @abstractmethod
    def move_conveyor(self, distance, speed):
        """
        Move the conveyor belt a certain distance at a given speed.
        """
        pass

    @abstractmethod
    def stop_conveyor(self):
        """
        Stop the conveyor belt.
        """
        pass

    @abstractmethod
    def move_arm_to_position(self, position_name):
        """
        Move the robotic arm to a predefined position (e.g., 'home', 'pickup', 'class1').
        """
        pass

    @abstractmethod
    def read_sensor(self):
        """
        Read the state of the photoelectric sensor.
        Returns True if an object is detected, False otherwise.
        """
        pass

    @abstractmethod
    def cleanup(self):
        """
        Clean up all hardware resources (e.g., release camera, GPIO cleanup).
        """
        pass
