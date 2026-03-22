"""
Standalone camera capture worker — runs in a subprocess.
Captures frames and writes JPEG to a shared file.
"""
import os
import sys
import time

# Must be set BEFORE importing cv2
os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0"

import cv2

FRAME_PATH = os.path.join(os.path.dirname(__file__), ".frame.jpg")
DEVICE_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
FPS = int(os.getenv("CAMERA_FPS", "15"))


def main():
    cap = cv2.VideoCapture(DEVICE_INDEX)
    if not cap.isOpened():
        print("[camera_worker] Failed to open camera", file=sys.stderr)
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, FPS)

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"[camera_worker] Camera opened: {w}x{h}", flush=True)

    interval = 1.0 / FPS
    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.05)
            continue

        _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        tmp = FRAME_PATH + ".tmp"
        with open(tmp, "wb") as f:
            f.write(jpeg.tobytes())
        os.replace(tmp, FRAME_PATH)

        time.sleep(interval)


if __name__ == "__main__":
    main()
