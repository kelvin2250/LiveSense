import argparse
import os
import sys
from pathlib import Path

from huggingface_hub import snapshot_download


def has_onnx_models(target_root: Path) -> bool:
    expected = [
        target_root / "interaction_model_onnx" / "model.onnx",
        target_root / "emotion_encoder_onnx" / "model.onnx",
        target_root / "toxicity_encoder_onnx" / "model.onnx",
    ]
    return all(path.exists() for path in expected)


def main() -> int:
    parser = argparse.ArgumentParser(description="Download ONNX model artifacts from Hugging Face")
    parser.add_argument("--repo-id", required=True, help="Hugging Face repo id, e.g. user/livesense-qoe-models")
    parser.add_argument("--target-dir", default="onnx_models", help="Local target directory for ONNX artifacts")
    parser.add_argument("--token", default=None, help="HF token (optional, required for private repos)")
    parser.add_argument("--force", action="store_true", help="Force re-download even if models already exist")
    args = parser.parse_args()

    target_dir = Path(args.target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    if has_onnx_models(target_dir) and not args.force:
        print(f"ONNX models already present in {target_dir}. Use --force to re-download.")
        return 0

    token = args.token or os.getenv("HF_TOKEN")

    try:
        snapshot_download(
            repo_id=args.repo_id,
            repo_type="model",
            local_dir=str(target_dir),
            allow_patterns=["*.onnx", "*.txt", "*.json", "*.model", "*.bin", "*.codes", "*.vocab", "*tokenizer*", "*config*"],
            token=token,
        )
    except Exception as exc:
        print(f"Failed to download models from {args.repo_id}: {exc}")
        return 1

    if not has_onnx_models(target_dir):
        print("Download completed, but required ONNX files are still missing. Check repo contents.")
        return 1

    print(f"Downloaded ONNX artifacts to {target_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
