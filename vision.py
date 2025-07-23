import cv2
from ultralytics import YOLO
import config

class VisionSystem:
    """
    Handles the object detection using the YOLO model.
    """

    def __init__(self):
        """
        Initializes the Vision System and loads the YOLO model.
        """
        print("Initializing Vision System...")
        try:
            self.model = YOLO(config.MODEL_PATH)
            print(f"YOLO model '{config.MODEL_NAME}' loaded successfully.")
            # Perform a dummy inference to warm up the model
            warmup_image_path = 'test_image.jpg'
            if os.path.exists(warmup_image_path):
                dummy_frame = cv2.imread(warmup_image_path)
                if dummy_frame is not None:
                    self.model(dummy_frame, verbose=False)
                    print("Model warmed up with 'test_image.jpg'.")
            else:
                print("Warmup skipped: 'test_image.jpg' not found.")
        except Exception as e:
            print(f"Error loading YOLO model: {e}")
            print("Please ensure the model file exists at:", config.MODEL_PATH)
            self.model = None

    def _preprocess_image(self, frame):
        """
        Applies preprocessing steps to the image before inference.
        - High-boost filtering (sharpening)
        - Edge detection (Canny) - for visualization/logging, not for YOLO input
        """
        # 1. High-Boost Filtering (Sharpening)
        # Using a sharpening kernel
        sharpen_kernel = np.array([[-1, -1, -1],
                                   [-1,  9, -1],
                                   [-1, -1, -1]])
        sharpened_frame = cv2.filter2D(frame, -1, sharpen_kernel)

        # 2. Edge Detection (Canny)
        # Convert to grayscale for Canny
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # Apply Gaussian blur to reduce noise
        blurred_frame = cv2.GaussianBlur(gray_frame, (5, 5), 0)
        # Apply Canny edge detection
        edges = cv2.Canny(blurred_frame, 50, 150)

        # We will return the sharpened frame for YOLO inference,
        # and the edges for potential display or logging.
        return sharpened_frame, edges

    def run_inference(self, frame):
        """
        Runs inference on a single frame after preprocessing.

        Args:
            frame (np.ndarray): The input image in BGR format.

        Returns:
            tuple: A tuple containing:
                - results (list): A list of detected objects. Each object is a dict.
                - annotated_frame (np.ndarray): The frame with bounding boxes drawn on it.
                - edges (np.ndarray): The Canny edge detection result.
        """
        if self.model is None:
            print("Model not loaded, skipping inference.")
            return [], frame, cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Preprocess the image
        preprocessed_frame, edges = self._preprocess_image(frame)

        # Perform inference on the preprocessed (sharpened) frame
        results = self.model(preprocessed_frame, verbose=False)

        # Annotate the original frame with results for a clearer view
        annotated_frame = results[0].plot(img=frame.copy())

        # Process results
        detected_objects = []
        for r in results:
            for box in r.boxes:
                # Get bounding box coordinates
                x1, y1, x2, y2 = box.xyxy[0]
                # Get confidence score
                confidence = box.conf[0]
                # Get class id
                class_id = int(box.cls[0])
                # Get class name
                class_name = self.model.names[class_id]

                detected_objects.append({
                    'class_name': class_name,
                    'confidence': float(confidence),
                    'bbox': [int(x1), int(y1), int(x2), int(y2)]
                })

        return detected_objects, annotated_frame, edges

if __name__ == '__main__':
    # A simple test for the VisionSystem
    # Make sure you have a 'test_image.jpg' in your project root for this to work
    vision = VisionSystem()
    if vision.model:
        test_image = cv2.imread('test_image.jpg')
        if test_image is not None:
            detections, output_image = vision.run_inference(test_image)
            print("Detections:", detections)
            cv2.imshow("Inference Result", output_image)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        else:
            print("Could not read 'test_image.jpg'.")
