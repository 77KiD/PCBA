import os
import cv2
import base64
import platform
import threading
import time
from flask import Flask, render_template, Response
from flask_socketio import SocketIO

import config
from vision import VisionSystem

# --- Global Variables ---
app = Flask(__name__)
socketio = SocketIO(app)
vision_system = VisionSystem()
hardware_controller = None
automation_thread = None
stop_event = threading.Event()

# --- Hardware Controller Initialization ---
def initialize_hardware():
    """Dynamically initializes the hardware controller based on the OS."""
    global hardware_controller
    system = platform.system()
    if system == "Linux":
        # Assume it's Jetson
        from hardware_control.jetson import JetsonController
        try:
            hardware_controller = JetsonController(config)
            print("Jetson Controller Initialized.")
        except Exception as e:
            print(f"Could not initialize Jetson Controller: {e}")
            print("Falling back to Windows Simulation Controller.")
            from hardware_control.windows import WindowsController
            hardware_controller = WindowsController(config)
    else:
        # Windows or other OS
        from hardware_control.windows import WindowsController
        hardware_controller = WindowsController(config)
        print("Windows Simulation Controller Initialized.")

# --- Main Automation Logic ---
# --- Global State ---
# This dictionary holds the latest frames for streaming
latest_frames = {
    'raw': None,
    'annotated': None
}
lock = threading.Lock()

def automation_loop():
    """The main loop for the automated process."""
    global latest_frames
    print("Automation loop started.")

    while not stop_event.is_set():
        socketio.emit('log', {'message': '步驟 1: 等待光電感測器觸發...'})

        # Wait for the sensor to be triggered, checking for the stop event periodically
        while not hardware_controller.read_sensor():
            if stop_event.is_set():
                break
            time.sleep(0.1)

        if stop_event.is_set():
            break

        socketio.emit('log', {'message': '偵測到物體!'})
        time.sleep(0.5) # Debounce and allow object to settle

        socketio.emit('log', {'message': '步驟 2: 擷取影像並執行推論...'})
        frame = hardware_controller.capture_image()

        if frame is None:
            socketio.emit('log', {'message': '錯誤: 無法擷取影像。'})
            time.sleep(1)
            continue

        # Store the raw frame for the video feed
        with lock:
            latest_frames['raw'] = frame.copy()

        # Run inference
        detections, annotated_frame, _ = vision_system.run_inference(frame)
        with lock:
            latest_frames['annotated'] = annotated_frame.copy()

        # Determine result
        if detections:
            result = "缺陷"
            # Combine all detected defect types for logging
            defect_type = ', '.join(list(set([d['class_name'] for d in detections])))
        else:
            result = "合格"
            defect_type = "無"

        socketio.emit('detection_result', {'result': result, 'defect_type': defect_type})
        socketio.emit('log', {'message': f'推論完成: {result} (瑕疵: {defect_type})'})

        socketio.emit('log', {'message': '步驟 3: 移動輸送帶至夾取點...'})
        hardware_controller.move_conveyor(distance=15, speed=70) # Calibrate these values
        time.sleep(1) # Wait for conveyor

        socketio.emit('log', {'message': '步驟 4: 控制機械手臂進行分類...'})
        hardware_controller.move_arm_to_position('pickup')

        if result == "合格":
            socketio.emit('log', {'message': '判定為合格品，移至分類區 1。'})
            hardware_controller.move_arm_to_position('class1')
        else:
            socketio.emit('log', {'message': f'判定為缺陷品 ({defect_type})，移至分類區 2。'})
            hardware_controller.move_arm_to_position('class2')

        # Return arm to home position
        hardware_controller.move_arm_to_position('home')
        socketio.emit('log', {'message': '機械手臂歸位，流程完成。'})

        # Clear the annotated frame after the process is done
        with lock:
            latest_frames['annotated'] = None

        # Wait a bit before starting the next cycle
        time.sleep(1)

    print("Automation loop stopped.")


# --- Flask Routes ---
@app.route('/')
def index():
    """Renders the main web page."""
    return render_template('index.html')

def gen_frames():
    """
    Generator function for video streaming.
    It streams the annotated frame if available, otherwise the raw frame.
    """
    while True:
        with lock:
            # Prioritize showing the annotated frame if it exists
            if latest_frames['annotated'] is not None:
                frame_to_show = latest_frames['annotated']
            # Fallback to the raw camera feed
            elif hardware_controller:
                 # Capture a fresh raw frame if not in an automation cycle
                if latest_frames['raw'] is None:
                     latest_frames['raw'] = hardware_controller.capture_image()
                frame_to_show = latest_frames['raw']
            else:
                # If hardware is not ready, don't stream
                time.sleep(0.1)
                continue

        if frame_to_show is not None:
            try:
                _, buffer = cv2.imencode('.jpg', frame_to_show)
                frame_bytes = buffer.tobytes()
                # Emit the frame via SocketIO
                socketio.emit('video_frame', {'frame': base64.b64encode(frame_bytes).decode('utf-8')})
            except Exception as e:
                print(f"Error encoding frame: {e}")

        socketio.sleep(0.05) # Control streaming rate (~20fps)

@app.route('/video_feed')
def video_feed():
    """This route is no longer the primary method for video streaming but is kept for potential fallback or testing."""
    return Response("Video streaming is now handled by SocketIO.", mimetype='text/plain')


# --- SocketIO Events ---
@socketio.on('connect')
def handle_connect():
    """Handles new client connections."""
    print('Client connected')
    socketio.emit('update_status', {'status': 'Connected', 'badge': 'badge-primary'})
    # Start sending video frames
    if not hasattr(handle_connect, "video_thread") or not handle_connect.video_thread.is_alive():
        handle_connect.video_thread = socketio.start_background_task(target=gen_frames)


@socketio.on('control_event')
def handle_control_event(json):
    """Handles control commands from the client."""
    global automation_thread
    action = json.get('action')

    if action == 'start':
        if automation_thread is None or not automation_thread.is_alive():
            stop_event.clear()
            automation_thread = threading.Thread(target=automation_loop)
            automation_thread.start()
            socketio.emit('update_status', {'status': 'Running', 'badge': 'badge-success'})
            print("Automation started.")

    elif action == 'stop':
        if automation_thread and automation_thread.is_alive():
            stop_event.set()
            automation_thread.join()
        socketio.emit('update_status', {'status': 'Stopped', 'badge': 'badge-danger'})
        hardware_controller.stop_conveyor()
        hardware_controller.move_arm_to_position('home')
        print("Automation stopped.")

    elif action == 'manual_conveyor':
        hardware_controller.move_conveyor(10, 50)
        socketio.emit('log', {'message': 'Manual conveyor movement requested.'})

    elif action == 'manual_arm_home':
        hardware_controller.move_arm_to_position('home')
        socketio.emit('log', {'message': 'Manual arm home requested.'})


if __name__ == '__main__':
    initialize_hardware()
    print("Starting Flask server...")
    # use_reloader=False is important to prevent running initialization twice
    # allow_unsafe_werkzeug=True is required for debug mode with recent versions of Werkzeug
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False, allow_unsafe_werkzeug=True)

    # Cleanup on exit
    if hardware_controller:
        hardware_controller.cleanup()
