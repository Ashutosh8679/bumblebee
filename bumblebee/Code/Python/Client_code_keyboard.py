import socket
import sys
import termios
import tty
import time
import cv2
import threading
import numpy as np

# ================= ESP32 SETTINGS =================
ESP32_IP = "192.168.4.1"
ESP32_PORT = 3333
ESP_STREAM_URL = "http://192.168.4.2/stream"
WINDOW_NAME = "ESP32-CAM Stream"

# ================= UDP SOCKET =================
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setblocking(False)

# ================= SHARED STATE =================
esp_frame = None
esp_lock = threading.Lock()
running = True
last_cmd = "—"

print("ESP32 UDP Car Controller with Live Stream")
print("------------------------------------------")
print("Controls:")
print("  W → Forward")
print("  S → Backward")
print("  A → Left")
print("  D → Right")
print("  Space → Stop")
print("  Q → Quit")
print("------------------------------------------")

# ================= ESP32-CAM STREAM THREAD =================
def esp_cam_loop():
    global esp_frame, running
    while running:
        cap = cv2.VideoCapture(ESP_STREAM_URL)
        if not cap.isOpened():
            print("Waiting for ESP32-CAM stream...")
            time.sleep(2)
            continue

        print("✓ ESP32-CAM stream connected!")
        
        while running:
            ok, frame = cap.read()
            if not ok:
                print("Lost ESP32-CAM connection, reconnecting...")
                break
            with esp_lock:
                esp_frame = frame.copy()

        cap.release()
        time.sleep(1)

# Start camera stream thread
threading.Thread(target=esp_cam_loop, daemon=True).start()

# ================= KEYBOARD INPUT =================
def get_key():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        key = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return key

def send(cmd):
    global last_cmd
    sock.sendto(cmd.encode(), (ESP32_IP, ESP32_PORT))
    last_cmd = cmd
    print(f"Sent: {cmd}")

# ================= DISPLAY THREAD =================
def display_stream():
    global running
    
    # Wait for first frame
    time.sleep(1)
    
    while running:
        with esp_lock:
            frame = esp_frame.copy() if esp_frame is not None else None
        
        if frame is None:
            # Show offline message
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(
                frame, "ESP32-CAM OFFLINE",
                (120, 240),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.2, (0, 0, 255), 3
            )
        else:
            frame = cv2.resize(frame, (640, 480))
        
        # Add command overlay
        cv2.putText(
            frame, f"Last Command: {last_cmd}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0, (0, 255, 0), 2
        )
        
        # Add controls reminder
        controls = "W:FWD S:BACK A:LEFT D:RIGHT SPACE:STOP Q:QUIT"
        cv2.putText(
            frame, controls,
            (10, 460),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5, (255, 255, 255), 1
        )
        
        cv2.imshow(WINDOW_NAME, frame)
        
        # Check for window close or ESC key
        key = cv2.waitKey(1)
        if key == 27 or cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
            running = False
            break

# Start display thread
threading.Thread(target=display_stream, daemon=True).start()

# ================= MAIN KEYBOARD CONTROL LOOP =================
try:
    while running:
        key = get_key().lower()
        
        if key == 'w':
            send('F')
        elif key == 's':
            send('B')
        elif key == 'a':
            send('L')
        elif key == 'd':
            send('R')
        elif key == ' ':
            send('S')
        elif key == 'q':
            send('S')
            print("Exiting...")
            running = False
            break
        
        time.sleep(0.05)
        
except KeyboardInterrupt:
    send('S')
    print("\nInterrupted, motors stopped.")
    running = False

# Cleanup
cv2.destroyAllWindows()
print("Stream closed.")