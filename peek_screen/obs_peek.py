from __future__ import annotations

import threading
import time
from collections import deque
from contextlib import asynccontextmanager

import cv2
import numpy as np
import uvicorn
from fastapi import FastAPI, Response

# Configuration
OBS_CAM_INDEX = 2      # Index of OBS Virtual Camera (adjust if multiple cameras exist)
TARGET_HEIGHT = 480    # 480p standard height
TARGET_WIDTH = 854     # 16:9 480p width
BUFFER_CAPACITY = 6    # Ring buffer size (6 to 8 frames)
CAPTURE_FPS = 1.0      # 1 frame per second

MIN_FPS = 0.1       # Idle: 1 frame every 10 seconds (near 0% CPU)
MAX_FPS = 1.0       # Active cap: 1 frame per second
AI_STEP = 0.5      # Additive Increase (+0.25 FPS per request hit)
MD_FACTOR = 0.5     # Multiplicative Decrease (halves FPS when idle)
IDLE_TIMEOUT = 10.0  # Seconds of silence before decay triggers

class AIMDController:
    """Manages dynamic sampling rate using AIMD state logic."""
    def __init__(self, min_fps: float = MIN_FPS, max_fps: float = MAX_FPS, ai_step: float = AI_STEP, md_factor: float = MD_FACTOR, timeout: float = IDLE_TIMEOUT):
        self.min_fps = min_fps
        self.max_fps = max_fps
        self.ai_step = ai_step
        self.md_factor = md_factor
        self.timeout = timeout

        self.current_fps = min_fps
        self.last_request_time = 0.0
        self.lock = threading.Lock()

    def record_request(self):
        """Called on HTTP GET: Additive Increase."""
        with self.lock:
            self.last_request_time = time.time()
            self.current_fps = min(self.max_fps, self.current_fps + self.ai_step)
            return self.current_fps

    def evaluate_decay(self):
        """Called periodically: Multiplicative Decrease if idle."""
        with self.lock:
            now = time.time()
            if now - self.last_request_time > self.timeout:
                self.current_fps = max(self.min_fps, self.current_fps * self.md_factor)
            return self.current_fps


class OBSFrameBuffer:
    def __init__(self, camera_index: int = OBS_CAM_INDEX, maxlen: int = BUFFER_CAPACITY):
        self.camera_index = camera_index
        self.ring_buffer = deque(maxlen=maxlen)
        self.aimd = AIMDController()
        self.lock = threading.Lock()
        self.running = False
        self.producer_thread = None
        self.cached_grid_jpeg = b""
        self.dirty_grid = False

    def start(self):
        self.running = True
        self.producer_thread = threading.Thread(target=self._producer_loop, daemon=True)
        self.producer_thread.start()

    def stop(self):
        self.running = False
        if self.producer_thread:
            self.producer_thread.join()

    def _producer_loop(self) -> None:
        # Open camera with explicit lower resolution request if supported by driver
        cap = cv2.VideoCapture(self.camera_index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, TARGET_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, TARGET_HEIGHT)

        last_capture_time = 0.0

        while self.running:
            # Drain camera stream buffer efficiently using grab()
            grabbed = cap.grab()
            if not grabbed:
                time.sleep(0.01)
                continue

            # Check AIMD decay state
            current_fps = self.aimd.evaluate_decay()
            interval = 1.0 / current_fps
            now = time.time()

            # Decode frame only at AIMD-governed interval
            if now - last_capture_time >= interval:
                last_capture_time = now
                ret, frame = cap.retrieve()

                if ret:
                    if frame.shape[0] != TARGET_HEIGHT or frame.shape[1] != TARGET_WIDTH:
                        frame = cv2.resize(frame, (TARGET_WIDTH, TARGET_HEIGHT), interpolation=cv2.INTER_NEAREST)

                    timestamp_str = f"{time.strftime('%H:%M:%S')} ({current_fps:.2f} FPS)"
                    cv2.putText(frame, timestamp_str, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                    with self.lock:
                        self.ring_buffer.append(frame)
                        self.dirty_grid = True

            # Adaptive sleep based on active FPS rate
            time.sleep(min(0.1, 1.0 / current_fps))

        cap.release()

    def get_grid_jpeg(self) -> bytes:
        # Notify AIMD controller of API request (Additive Increase)
        self.aimd.record_request()

        with self.lock:
            # Lazy rendering: encode JPEG only if ring buffer was updated
            if self.dirty_grid or not self.cached_grid_jpeg:
                self._render_grid_jpeg()
                self.dirty_grid = False
            return self.cached_grid_jpeg

    def _render_grid_jpeg(self, cols: int = 3) -> None:
        frames = list(self.ring_buffer)
        if not frames:
            blank = np.zeros((TARGET_HEIGHT, TARGET_WIDTH, 3), dtype=np.uint8)
            _, encoded = cv2.imencode('.jpg', blank)
            self.cached_grid_jpeg = encoded.tobytes()
            return

        num_frames = len(frames)
        rows = int(np.ceil(num_frames / cols))
        total_slots = rows * cols

        padded = frames + [np.zeros((TARGET_HEIGHT, TARGET_WIDTH, 3), dtype=np.uint8)] * (total_slots - num_frames)
        grid_rows = [np.hstack(padded[r * cols:(r + 1) * cols]) for r in range(rows)]
        grid = np.vstack(grid_rows)

        grid_small = cv2.resize(grid, (grid.shape[1] // 2, grid.shape[0] // 2), interpolation=cv2.INTER_NEAREST)
        _, encoded = cv2.imencode('.jpg', grid_small, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
        self.cached_grid_jpeg = encoded.tobytes()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Code executed on startup
    print("\n".join([str(route) for route in app.routes]))
    service.start()
    try:
        yield
    finally:
        # Code executed on shutdown
        service.stop()


# Initialize FastAPI app and frame collector
app = FastAPI(title="OBS Frame Buffer Service", lifespan=lifespan)
service = OBSFrameBuffer()

@app.get("/grid", response_class=Response)
def get_grid():
    """Returns the timeline composite grid image (JPEG)."""
    jpeg_data = service.get_grid_jpeg()
    return Response(content=jpeg_data, media_type="image/jpeg")

@app.get("/status")
def status():
    """Returns status and current frame count in ring buffer."""
    return {
        "current_fps": service.aimd.current_fps,
        "buffer_size": len(service.ring_buffer),
        "idle_seconds": round(time.time() - service.aimd.last_request_time, 2)
    }


if __name__ == "__main__":
    # Runs the background API service on http://127.0.0.1:8000
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
