from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List

import requests

from .rubric import RUBRIC


def extract_json(text: str) -> Dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I | re.S)
    return json.loads(cleaned)


def _data_url(path: str) -> str:
    mime = mimetypes.guess_type(path)[0] or "image/jpeg"
    payload = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    return f"data:{mime};base64,{payload}"


def _selected_frames(manifest: Dict[str, Any], max_frames: int) -> Iterable[Dict[str, Any]]:
    frames = [frame for shot in manifest["shots"] for frame in shot.get("keyframes", [])]
    if len(frames) <= max_frames:
        return frames
    indices = [round(i * (len(frames) - 1) / (max_frames - 1)) for i in range(max_frames)]
    return [frames[index] for index in sorted(set(indices))]


def _video_content(name: str, manifest: Dict[str, Any], max_frames: int) -> List[Dict[str, Any]]:
    content: List[Dict[str, Any]] = [{
        "type": "text",
        "text": f"{name}：时长 {manifest['duration']} 秒，共 {len(manifest['shots'])} 个检测镜头。以下图片按时间顺序排列。",
    }]
    for frame in _selected_frames(manifest, max_frames):
        content.append({"type": "text", "text": f"证据标签：{frame['label']}"})
        content.append({"type": "image_url", "image_url": {"url": _data_url(frame["path"]), "detail": "low"}})
    return content


def evaluate(original: Dict[str, Any], remake: Dict[str, Any], instruction: str, max_frames: int = 24) -> Dict[str, Any]:
    base_url = os.environ.get("API_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    api_key = os.environ.get("API_KEY")
    model = os.environ.get("MODEL", "gpt-4.1-mini")
    if not api_key:
        raise RuntimeError("缺少 API_KEY。请复制 .env.example 为 .env 并填写可用密钥。")

    user_content: List[Dict[str, Any]] = [{"type": "text", "text": f"用户修改指令：{instruction}"}]
    user_content.extend(_video_content("原视频", original, max_frames))
    user_content.extend(_video_content("复刻视频", remake, max_frames))

    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": RUBRIC},
            {"role": "user", "content": user_content},
        ],
    }
    response = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=180,
    )
    response.raise_for_status()
    body = response.json()
    text = body["choices"][0]["message"]["content"]
    result = extract_json(text)
    result["meta"] = {"model": model, "max_frames_per_video": max_frames}
    return result
