from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import imageio_ffmpeg
import requests

from .evaluator import _data_url, extract_json


def _api_settings(model_env: str, default_model: str) -> tuple[str, str, str]:
    base_url = os.environ.get("API_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    api_key = os.environ.get("API_KEY")
    if not api_key:
        raise RuntimeError("启用 ASR/OCR 时需要在 .env 中配置 API_KEY。")
    return base_url, api_key, os.environ.get(model_env, default_model)


def extract_audio(video_path: Path, audio_path: Path) -> Path:
    """使用随项目安装的 ffmpeg 从视频提取 16kHz 单声道音频。"""
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", str(video_path),
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(audio_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"音频提取失败：{result.stderr[-800:]}")
    return audio_path


def transcribe_video(video_path: Path, output_dir: Path) -> Dict[str, Any]:
    """提取音频并调用 OpenAI-compatible transcription API，保留分段时间戳。"""
    base_url, api_key, model = _api_settings("ASR_MODEL", "whisper-1")
    audio_path = extract_audio(video_path, output_dir / "audio.wav")
    with audio_path.open("rb") as audio:
        response = requests.post(
            f"{base_url}/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (audio_path.name, audio, "audio/wav")},
            data={"model": model, "response_format": "verbose_json", "timestamp_granularities[]": "segment"},
            timeout=300,
        )
    response.raise_for_status()
    body = response.json()
    result = {
        "model": model,
        "text": body.get("text", ""),
        "segments": [
            {
                "start": round(float(segment.get("start", 0)), 3),
                "end": round(float(segment.get("end", 0)), 3),
                "text": str(segment.get("text", "")).strip(),
            }
            for segment in body.get("segments", [])
        ],
    }
    (output_dir / "transcript.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def _sample_evenly(items: List[Dict[str, Any]], maximum: int) -> List[Dict[str, Any]]:
    if len(items) <= maximum:
        return items
    if maximum <= 1:
        return items[:1]
    indices = [round(i * (len(items) - 1) / (maximum - 1)) for i in range(maximum)]
    return [items[index] for index in sorted(set(indices))]


def recognize_frame_text(manifest: Dict[str, Any], output_dir: Path, max_frames: int = 24) -> Dict[str, Any]:
    """调用视觉模型专门识别关键帧中的字幕、标题、标牌等可见文字。"""
    base_url, api_key, model = _api_settings("OCR_MODEL", os.environ.get("MODEL", "gpt-4.1-mini"))
    frames = [frame for shot in manifest["shots"] for frame in shot.get("keyframes", [])]
    frames = _sample_evenly(frames, max_frames)
    content: List[Dict[str, Any]] = [{
        "type": "text",
        "text": (
            "请逐张识别图片里清晰可见的文字，包括字幕、标题、标牌和道具文字。"
            "不要描述画面，不确定时留空，不要猜测。只输出合法 JSON："
            '{"frames":[{"label":"原标签","texts":["文字1"],"confidence":"high|medium|low"}]}'
        ),
    }]
    for frame in frames:
        content.append({"type": "text", "text": f"图片标签：{frame['label']}"})
        content.append({"type": "image_url", "image_url": {"url": _data_url(frame["path"]), "detail": "high"}})

    response = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "temperature": 0,
            "messages": [{"role": "user", "content": content}],
        },
        timeout=300,
    )
    response.raise_for_status()
    parsed = extract_json(response.json()["choices"][0]["message"]["content"])
    result = {"model": model, "frames": parsed.get("frames", [])}
    (output_dir / "ocr.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def attach_evidence(manifest: Dict[str, Any], transcript: Optional[Dict[str, Any]] = None, ocr: Optional[Dict[str, Any]] = None) -> None:
    """把 ASR/OCR 结果挂到对应镜头和关键帧，供最终 Judge 按时间顺序读取。"""
    transcript_segments = (transcript or {}).get("segments", [])
    ocr_by_label = {item.get("label"): item for item in (ocr or {}).get("frames", [])}
    for shot in manifest["shots"]:
        shot["asr_segments"] = [
            segment for segment in transcript_segments
            if segment["end"] >= shot["start"] and segment["start"] <= shot["end"]
        ]
        for frame in shot.get("keyframes", []):
            item = ocr_by_label.get(frame["label"], {})
            frame["ocr_texts"] = item.get("texts", [])
            if item.get("confidence"):
                frame["ocr_confidence"] = item["confidence"]
