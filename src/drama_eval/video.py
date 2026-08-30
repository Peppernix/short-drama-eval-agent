from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import cv2


def _frame_distance(previous, current) -> float:
    previous = cv2.resize(previous, (160, 90))
    current = cv2.resize(current, (160, 90))
    previous = cv2.cvtColor(previous, cv2.COLOR_BGR2HSV)
    current = cv2.cvtColor(current, cv2.COLOR_BGR2HSV)
    hist_a = cv2.calcHist([previous], [0, 1], None, [32, 32], [0, 180, 0, 256])
    hist_b = cv2.calcHist([current], [0, 1], None, [32, 32], [0, 180, 0, 256])
    cv2.normalize(hist_a, hist_a)
    cv2.normalize(hist_b, hist_b)
    return float(cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_BHATTACHARYYA))


def detect_shots(video_path: Path, threshold: float = 0.48, sample_fps: float = 2.0) -> Dict[str, Any]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"无法读取视频：{video_path}")

    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count / fps if fps else 0.0
    step = max(1, int(round(fps / sample_fps)))

    boundaries: List[float] = [0.0]
    previous = None
    frame_index = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        if frame_index % step == 0:
            if previous is not None and _frame_distance(previous, frame) >= threshold:
                timestamp = frame_index / fps
                if timestamp - boundaries[-1] >= 0.5:
                    boundaries.append(timestamp)
            previous = frame
        frame_index += 1
    capture.release()

    if duration > boundaries[-1]:
        boundaries.append(duration)
    if len(boundaries) == 1:
        boundaries.append(duration)

    shots = []
    for index, (start, end) in enumerate(zip(boundaries[:-1], boundaries[1:]), 1):
        if end - start >= 0.15:
            shots.append({"shot_id": index, "start": round(start, 3), "end": round(end, 3)})

    return {
        "source": str(video_path.resolve()),
        "fps": round(fps, 3),
        "frame_count": frame_count,
        "duration": round(duration, 3),
        "shots": shots,
    }


def _timestamps_for_shot(start: float, end: float, max_gap: float = 4.0) -> List[float]:
    duration = max(0.0, end - start)
    points = [start + min(0.08, duration / 4), (start + end) / 2, max(start, end - min(0.08, duration / 4))]
    if duration > max_gap:
        count = int(duration // max_gap)
        points.extend(start + duration * i / (count + 1) for i in range(1, count + 1))
    return sorted({round(min(max(t, start), end), 3) for t in points})


def extract_keyframes(video_path: Path, manifest: Dict[str, Any], output_dir: Path, prefix: str) -> Dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"无法读取视频：{video_path}")

    for shot in manifest["shots"]:
        frames = []
        for timestamp in _timestamps_for_shot(shot["start"], shot["end"]):
            capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
            ok, frame = capture.read()
            if not ok:
                continue
            label = f"{prefix}_shot_{shot['shot_id']:03d}_t{timestamp:.2f}"
            path = output_dir / f"{label}.jpg"
            cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, 88])
            frames.append({"label": label, "timestamp": timestamp, "path": str(path.resolve())})
        shot["keyframes"] = frames

    capture.release()
    manifest_path = output_dir.parent / f"{prefix}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def prepare_video(video_path: Path, run_dir: Path, prefix: str, threshold: float) -> Dict[str, Any]:
    manifest = detect_shots(video_path, threshold=threshold)
    return extract_keyframes(video_path, manifest, run_dir / prefix / "frames", prefix)
