import cv2
import mediapipe as mp
import socket
import threading
import time
import numpy as np

# ================= ESP32 SETTINGS =================
ESP_IP = "192.168.4.1"          # ESP32-DEV (motors)
ESP_PORT = 3333

ESP_STREAM_URL = "http://192.168.4.2/stream"  # ESP32-CAM IP
WINDOW_NAME = "Robot Control Dashboard"

# ================= SHARED LOG STATE =================
log = {
    "tx": "—",
    "rx": "—"
}
log_lock = threading.Lock()

# ================= SHARED CONTROL STATE =================
state = {
    "gesture": "NONE",
    "active": "STOP"
}
state_lock = threading.Lock()
last_sent = None

# ================= UDP SEND =================
def send_message(msg):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(msg.encode(), (ESP_IP, ESP_PORT))
        s.close()
        with log_lock:
            log["tx"] = msg
    except:
        pass

# ================= UDP RECEIVE (OPTIONAL) =================
def rx_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", ESP_PORT))
    sock.settimeout(1.0)

    while True:
        try:
            data, addr = sock.recvfrom(64)
            with log_lock:
                log["rx"] = data.decode(errors="ignore")
        except:
            pass

threading.Thread(target=rx_listener, daemon=True).start()

# ================= MEDIAPIPE HAND SETUP (NEW API) =================
BaseOptions = mp.tasks.BaseOptions
HandLandmarker = mp.tasks.vision.HandLandmarker
HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
VisionRunningMode = mp.tasks.vision.RunningMode

# Download model from:
# https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task
model_path = 'hand_landmarker.task'

options = HandLandmarkerOptions(
    base_options=BaseOptions(model_asset_path=model_path),
    running_mode=VisionRunningMode.VIDEO,
    num_hands=1,
    min_hand_detection_confidence=0.7,
    min_hand_presence_confidence=0.6,
    min_tracking_confidence=0.6
)

landmarker = HandLandmarker.create_from_options(options)

def get_finger_list(landmarks):
    tips = [4, 8, 12, 16, 20]
    fingers = []

    fingers.append(1 if landmarks[tips[0]].x < landmarks[tips[0]-1].x else 0)
    for i in range(1, 5):
        fingers.append(1 if landmarks[tips[i]].y < landmarks[tips[i]-2].y else 0)

    return fingers

def gesture_to_action(f):
    if f == [0,0,0,0,0]: return "STOP"
    if f == [1,1,1,1,1]: return "FORWARD"
    if f == [0,1,0,0,0]: return "LEFT"
    if f == [0,1,1,0,0]: return "RIGHT"
    if f == [1,0,0,0,0]: return "BACK"
    return "NONE"

def action_to_cmd(a):
    return {
        "FORWARD": "F",
        "BACK": "B",
        "LEFT": "L",
        "RIGHT": "R",
        "STOP": "S"
    }.get(a, None)

def draw_landmarks(frame, hand_landmarks):
    """Draw hand landmarks on the frame."""
    h, w, _ = frame.shape
    
    # Draw connections
    connections = [
        (0, 1), (1, 2), (2, 3), (3, 4),  # Thumb
        (0, 5), (5, 6), (6, 7), (7, 8),  # Index
        (0, 9), (9, 10), (10, 11), (11, 12),  # Middle
        (0, 13), (13, 14), (14, 15), (15, 16),  # Ring
        (0, 17), (17, 18), (18, 19), (19, 20),  # Pinky
        (5, 9), (9, 13), (13, 17)  # Palm
    ]
    
    for connection in connections:
        start_idx, end_idx = connection
        start = hand_landmarks[start_idx]
        end = hand_landmarks[end_idx]
        
        start_point = (int(start.x * w), int(start.y * h))
        end_point = (int(end.x * w), int(end.y * h))
        
        cv2.line(frame, start_point, end_point, (255, 0, 0), 2)
    
    # Draw landmarks
    for landmark in hand_landmarks:
        x, y = int(landmark.x * w), int(landmark.y * h)
        cv2.circle(frame, (x, y), 5, (0, 255, 0), -1)

# ================= COMMAND ARBITER =================
def command_loop():
    global last_sent
    while True:
        with state_lock:
            cmd = state["active"]

        if cmd != last_sent:
            c = action_to_cmd(cmd)
            if c:
                send_message(c)
                last_sent = cmd

        time.sleep(0.05)

threading.Thread(target=command_loop, daemon=True).start()

# ================= ESP32-CAM THREAD =================
esp_frame = None
esp_lock = threading.Lock()

def esp_cam_loop():
    global esp_frame
    while True:
        cap = cv2.VideoCapture(ESP_STREAM_URL)
        if not cap.isOpened():
            time.sleep(2)
            continue

        while True:
            ok, frame = cap.read()
            if not ok:
                break
            with esp_lock:
                esp_frame = frame.copy()

        cap.release()
        time.sleep(1)

threading.Thread(target=esp_cam_loop, daemon=True).start()

# ================= WINDOW CLOSE DETECTION =================
def window_closed(name):
    return cv2.getWindowProperty(name, cv2.WND_PROP_VISIBLE) < 1

# ================= LOCAL CAMERA =================
hand_cam = cv2.VideoCapture(0)
frame_count = 0

print("Starting Robot Control Dashboard...")
print(f"Make sure '{model_path}' is in the same directory")
print("Press ESC to exit")

# ================= MAIN LOOP =================
while True:
    ok, hand_frame = hand_cam.read()
    if not ok:
        continue

    frame_count += 1
    hand_frame = cv2.flip(hand_frame, 1)
    
    # Convert to RGB for MediaPipe
    rgb = cv2.cvtColor(hand_frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    
    # Detect hands
    results = landmarker.detect_for_video(mp_image, frame_count)

    gesture = "NONE"

    if results.hand_landmarks:
        hand = results.hand_landmarks[0]
        draw_landmarks(hand_frame, hand)
        fingers = get_finger_list(hand)
        gesture = gesture_to_action(fingers)

    with state_lock:
        state["gesture"] = gesture
        state["active"] = gesture if gesture != "NONE" else "STOP"

    # -------- ESP32 FRAME OR FAILSAFE --------
    with esp_lock:
        ef = esp_frame.copy() if esp_frame is not None else None

    if ef is None:
        ef = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(
            ef, "ESP32-CAM OFFLINE",
            (90, 240),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0, (0,0,255), 3
        )
    else:
        ef = cv2.resize(ef, (640, 480))

    hand_frame = cv2.resize(hand_frame, (640, 480))
    dashboard = cv2.hconcat([ef, hand_frame])

    # -------- OVERLAY --------
    cv2.putText(dashboard, f"Gesture: {state['gesture']}",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0,255,0), 2)
    cv2.putText(dashboard, f"Active Cmd: {state['active']}",
                (10, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0,0,255), 2)

    # -------- LOG BAR --------
    log_bar_height = 50
    log_bar = np.zeros((log_bar_height, dashboard.shape[1], 3), dtype=np.uint8)

    with log_lock:
        tx = log["tx"]
        rx = log["rx"]

    log_text = f"TX → {tx}     RX ← {rx}"

    cv2.putText(
        log_bar,
        log_text,
        (10, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (255,255,255),
        2
    )

    dashboard = cv2.vconcat([dashboard, log_bar])

    cv2.imshow(WINDOW_NAME, dashboard)

    key = cv2.waitKey(1)
    if key == 27 or window_closed(WINDOW_NAME):
        break

hand_cam.release()
cv2.destroyAllWindows()