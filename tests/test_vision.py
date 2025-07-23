import cv2
import os
import sys
import numpy as np

# Add the root directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import config
from vision import VisionSystem
from hardware_control.windows import WindowsController

def create_test_image(path):
    """Creates a dummy image for testing if one doesn't exist."""
    if not os.path.exists(path):
        print(f"Creating a dummy test image at: {path}")
        # Create a black image with a white rectangle
        img = np.zeros((config.FRAME_HEIGHT, config.FRAME_WIDTH, 3), np.uint8)
        cv2.rectangle(img, (100, 100), (300, 300), (255, 255, 255), -1)
        cv2.putText(img, "TEST OBJECT", (110, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
        cv2.imwrite(path, img)

def main():
    """
    A test script for the VisionSystem module.
    """
    print("--- Running Vision System Test ---")

    # 1. Prepare a test image
    test_image_path = "test_image.jpg"
    create_test_image(test_image_path)

    # We need to tell the VisionSystem's dummy inference where to find an image
    # Let's modify the vision.py file to handle the case where the sample image doesn't exist.
    # For now, we proceed assuming the user will provide one.

    # 2. Initialize the Vision System
    # Note: This will try to load the real model. Make sure 'pcb_yolo12x_retry.pt' is in the 'models' folder.
    # If the model is not present, the test will still run but skip the inference part.
    vision = VisionSystem()

    if not vision.model:
        print("\nWARNING: YOLO model not found. Inference will be skipped.")
        print("Please place your '.pt' file in the 'models' directory and name it according to 'config.py'.")

    # 3. Initialize a (simulated) hardware controller
    # We use the Windows controller as it doesn't need real hardware.
    # Its capture_image() method will return a black frame, so we'll use our file-based image instead.
    print("\n--- Reading Test Image ---")
    image_to_test = cv2.imread(test_image_path)

    if image_to_test is None:
        print(f"Error: Could not read the test image at '{test_image_path}'")
        return

    print("Successfully read test image.")

    # 4. Run inference
    print("\n--- Running Inference ---")
    detections, annotated_frame, edges = vision.run_inference(image_to_test)

    # 5. Display results
    print(f"\nDetection Results: {detections}")

    if detections:
        print("Test PASSED: At least one object was detected.")
    else:
        if vision.model:
            print("Test WARNING: No objects were detected. This might be expected if the model is not trained for the dummy image.")
        else:
            print("Test SKIPPED: Inference was not performed as no model was loaded.")


    # Save the output images instead of displaying them
    output_dir = "test_outputs"
    os.makedirs(output_dir, exist_ok=True)

    annotated_path = os.path.join(output_dir, "annotated_test_image.jpg")
    edges_path = os.path.join(output_dir, "canny_edges.jpg")

    cv2.imwrite(annotated_path, annotated_frame)
    cv2.imwrite(edges_path, edges)

    print(f"\nOutput images saved to '{output_dir}' directory.")
    print(f" - Annotated image: {annotated_path}")
    print(f" - Edges image: {edges_path}")

    print("\n--- Vision System Test Finished ---")


if __name__ == '__main__':
    main()
