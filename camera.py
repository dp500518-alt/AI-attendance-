import cv2
import time
import base64
import numpy as np
import config

class CameraStream:
    def __init__(self, camera_index=None):
        self.camera_index = camera_index if camera_index is not None else config.CAMERA_INDEX
        self.cap = None

    def start(self):
        if self.cap is None or not self.cap.isOpened():
            self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW if cv2.os.name == 'nt' else cv2.CAP_ANY)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    def stop(self):
        if self.cap and self.cap.isOpened():
            self.cap.release()
            self.cap = None

    def get_frame(self):
        self.start()
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                return frame
        return None

    def generate_mjpeg_stream(self):
        self.start()
        while True:
            frame = self.get_frame()
            if frame is None:
                # Return placeholder if no physical webcam attached
                blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(blank_frame, "Camera Offline / Stream Active", (120, 240),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                _, jpeg = cv2.imencode('.jpg', blank_frame)
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
                time.sleep(0.5)
                continue

            ret, jpeg = cv2.imencode('.jpg', frame)
            if ret:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
            time.sleep(0.03)

def decode_base64_image(base64_str):
    """
    Decodes base64 string (data:image/jpeg;base64,...) from web browser into OpenCV BGR numpy array.
    """
    if ',' in base64_str:
        base64_str = base64_str.split(',')[1]

    img_data = base64.b64decode(base64_str)
    np_arr = np.frombuffer(img_data, np.uint8)
    img_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    return img_bgr

def encode_bgr_to_base64(img_bgr):
    """
    Encodes OpenCV BGR image array into base64 JPEG string for API response.
    """
    _, buffer = cv2.imencode('.jpg', img_bgr)
    b64_str = base64.b64encode(buffer).decode('utf-8')
    return f"data:image/jpeg;base64,{b64_str}"

camera_instance = CameraStream()
