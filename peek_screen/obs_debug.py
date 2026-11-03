from __future__ import annotations

import cv2
import numpy as np


def scan_and_dump_cameras(max_tested: int = 10, thumb_w: int = 320, thumb_h: int = 180) -> None:
    active_cameras = []
    thumbnails = []

    print("=" * 65)
    print(f"{'INDEX':<8} | {'STATUS':<12} | {'RESOLUTION':<12} | {'MEAN BRIGHTNESS'}")
    print("=" * 65)

    for idx in range(max_tested):
        # Try default backend (CAP_ANY) or specific backends if platform requires
        cap = cv2.VideoCapture(idx)

        if not cap.isOpened():
            cap.release()
            continue

        # Warm up buffer to grab actual frame
        ret = False
        frame = None
        for _ in range(5):
            ret, frame = cap.read()

        if ret and frame is not None:
            h, w, _ = frame.shape
            mean_val = float(np.mean(frame))
            is_black = mean_val < 2.0  # Threshold for pure dark/blank feeds

            status_str = "DARK / BLANK" if is_black else "ACTIVE"
            print(f"Cam [{idx}]  | {status_str:<12} | {w}x{h:<8} | Mean: {mean_val:.2f}")

            # Resize to thumbnail for grid
            thumb = cv2.resize(frame, (thumb_w, thumb_h))

            # Draw badge overlay
            label = f"Cam [{idx}] - {w}x{h} ({status_str})"
            color = (0, 0, 255) if is_black else (0, 255, 0)
            cv2.rectangle(thumb, (0, 0), (thumb_w, 25), (0, 0, 0), -1)
            cv2.putText(thumb, label, (8, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

            active_cameras.append(idx)
            thumbnails.append(thumb)
        else:
            print(f"Cam [{idx}]  | OPEN FAILED   | N/A          | N/A")

        cap.release()

    print("=" * 65)

    if not thumbnails:
        print("\n[!] No active camera feeds detected.")
        return

    # Build Grid Contact Sheet
    cols = min(3, len(thumbnails))
    rows = int(np.ceil(len(thumbnails) / cols))
    total_slots = rows * cols

    # Pad empty slots
    while len(thumbnails) < total_slots:
        blank = np.zeros((thumb_h, thumb_w, 3), dtype=np.uint8)
        cv2.putText(blank, "N/A", (thumb_w // 2 - 20, thumb_h // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (100, 100, 100), 2)
        thumbnails.append(blank)

    grid_rows = [np.hstack(thumbnails[r * cols:(r + 1) * cols]) for r in range(rows)]
    grid = np.vstack(grid_rows)

    output_filename = "camera_debug_grid.jpg"
    cv2.imwrite(output_filename, grid)
    print(f"\n[+] Saved camera preview grid to: {output_filename}")
    print(f"[+] Total usable devices found: {len(active_cameras)} (Indices: {active_cameras})")


if __name__ == "__main__":
    scan_and_dump_cameras()
