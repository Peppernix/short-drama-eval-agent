from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from .comparison import compare_with_human
from .enrichment import attach_evidence, recognize_frame_text, transcribe_video
from .evaluator import evaluate
from .video import prepare_video


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="短剧一键复刻自动评测 Agent MVP")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="预处理两段视频并调用多模态模型评测")
    run.add_argument("--original", required=True, type=Path, help="原视频路径")
    run.add_argument("--remake", required=True, type=Path, help="复刻视频路径")
    run.add_argument("--instruction", required=True, help="用户修改指令")
    run.add_argument("--output", type=Path, default=Path("runs"), help="运行输出根目录")
    run.add_argument("--threshold", type=float, default=0.48, help="镜头切分阈值，越低越敏感")
    run.add_argument("--max-frames", type=int, default=24, help="每段视频最多发送的关键帧数")
    run.add_argument("--with-asr", action="store_true", help="提取语音和分段时间戳，辅助剧情与台词评测")
    run.add_argument("--with-ocr", action="store_true", help="识别关键帧文字，辅助字幕与画面文字评测")
    run.add_argument("--prepare-only", action="store_true", help="只做预处理，不执行最终综合评测")

    compare = sub.add_parser("compare", help="比较一条机评结果与人工黄金答案")
    compare.add_argument("--machine", required=True, type=Path, help="evaluation.json 路径")
    compare.add_argument("--gold", required=True, type=Path, help="人工黄金样本 JSON 路径")
    compare.add_argument("--output", type=Path, help="可选：保存比较结果的 JSON 路径")
    return parser


def main() -> None:
    load_dotenv()
    args = build_parser().parse_args()
    if args.command == "compare":
        machine = json.loads(args.machine.read_text(encoding="utf-8"))
        gold = json.loads(args.gold.read_text(encoding="utf-8"))
        result = compare_with_human(machine, gold)
        if args.output:
            _write_json(args.output, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    for path in (args.original, args.remake):
        if not path.exists():
            raise SystemExit(f"文件不存在：{path}")

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = args.output / run_id
    original = prepare_video(args.original, run_dir, "original", args.threshold)
    remake = prepare_video(args.remake, run_dir, "remake", args.threshold)

    for source, manifest, prefix in (
        (args.original, original, "original"),
        (args.remake, remake, "remake"),
    ):
        transcript = transcribe_video(source, run_dir / prefix) if args.with_asr else None
        ocr = recognize_frame_text(manifest, run_dir / prefix, args.max_frames) if args.with_ocr else None
        attach_evidence(manifest, transcript, ocr)
        _write_json(run_dir / f"{prefix}_manifest.json", manifest)

    request = {
        "instruction": args.instruction,
        "original": str(args.original.resolve()),
        "remake": str(args.remake.resolve()),
        "with_asr": args.with_asr,
        "with_ocr": args.with_ocr,
    }
    _write_json(run_dir / "request.json", request)

    if args.prepare_only:
        print(f"预处理完成：{run_dir.resolve()}")
        return

    result = evaluate(original, remake, args.instruction, args.max_frames)
    _write_json(run_dir / "evaluation.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n结果目录：{run_dir.resolve()}", file=sys.stderr)


if __name__ == "__main__":
    main()
