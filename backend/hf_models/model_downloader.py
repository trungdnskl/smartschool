"""
HuggingFace Model Downloader - Classroom Engagement System
==========================================================
Tải và cache các models từ HuggingFace Hub vào thư mục local.

Models được tải:
1. Emotion Recognition - triac/mobileNet-facial-emotion  (nhẹ, CPU-friendly)
2. Emotion Recognition (backup) - dima806/facial_emotions_image_detection
3. Face Detection - deepface/retinaface (qua deepface library)
4. Attention/Head Pose - mediapipe (local, không cần HF)

Dataset được tải (optional / nhỏ):
- Dataset mẫu nhỏ để test pipeline
"""

import os
import sys
import logging
import json
import time
import hashlib
import shutil
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Thư mục lưu models
# ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent.parent   # e:\New folder (3)\classroom
MODELS_CACHE_DIR = BASE_DIR / "models_cache"
HF_MODELS_DIR    = MODELS_CACHE_DIR / "huggingface"
DATASETS_DIR     = MODELS_CACHE_DIR / "datasets"
LOGS_DIR         = MODELS_CACHE_DIR / "logs"

for _d in [HF_MODELS_DIR, DATASETS_DIR, LOGS_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# ──────────────────────────────────────────────────────────────
# Danh sách models cần tải
# ──────────────────────────────────────────────────────────────
EMOTION_MODELS = [
    {
        "name": "facial_emotions_primary",
        "model_id": "dima806/facial_emotions_image_detection",
        "task": "image-classification",
        "description": "Nhận dạng 7 cảm xúc cơ bản - accuracy ~93%, nhẹ 27MB",
        "labels": ["angry","disgust","fear","happy","neutral","sad","surprise"],
        "input_size": 224,
        "priority": 1,
    },
    {
        "name": "fer_emotion_resnet",
        "model_id": "Rajaram1996/Facial_Emotion_Recognition",
        "task": "image-classification",
        "description": "Facial Emotion Recognition ResNet - phụ",
        "labels": ["angry","disgust","fear","happy","neutral","sad","surprise"],
        "input_size": 48,
        "priority": 2,
    },
]

FACE_RECOGNITION_MODELS = [
    {
        "name": "arcface_insight",
        "model_id": "minchul/arcface_r100_glint360k",
        "task": "feature-extraction",
        "description": "ArcFace R100 - nhận diện khuôn mặt accuracy 99.7%",
        "input_size": 112,
        "priority": 1,
    },
]

ATTENTION_MODELS: list = []  # MediaPipe handles this locally


# ──────────────────────────────────────────────────────────────
# Status / progress tracking
# ──────────────────────────────────────────────────────────────

def _load_download_status() -> Dict[str, Any]:
    status_file = MODELS_CACHE_DIR / "download_status.json"
    if status_file.exists():
        try:
            return json.loads(status_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_download_status(status: Dict[str, Any]):
    status_file = MODELS_CACHE_DIR / "download_status.json"
    status_file.write_text(
        json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _mark_downloaded(model_name: str, model_id: str, save_path: str):
    status = _load_download_status()
    status[model_name] = {
        "model_id": model_id,
        "save_path": save_path,
        "downloaded_at": time.strftime("%Y-%m-%d %Human:%M:%S"),
        "status": "ok",
    }
    _save_download_status(status)


def _is_downloaded(model_name: str) -> bool:
    status = _load_download_status()
    entry = status.get(model_name, {})
    if entry.get("status") != "ok":
        return False
    save_path = entry.get("save_path", "")
    return bool(save_path) and Path(save_path).exists()


# ──────────────────────────────────────────────────────────────
# Kiểm tra thư viện
# ──────────────────────────────────────────────────────────────

def _check_huggingface_hub() -> bool:
    try:
        import huggingface_hub  # noqa
        return True
    except ImportError:
        return False


def _check_transformers() -> bool:
    try:
        import transformers  # noqa
        return True
    except ImportError:
        return False


def _check_torch() -> bool:
    try:
        import torch  # noqa
        return True
    except ImportError:
        return False


def _check_datasets_lib() -> bool:
    try:
        import datasets  # noqa
        return True
    except ImportError:
        return False


def get_library_status() -> Dict[str, bool]:
    return {
        "huggingface_hub": _check_huggingface_hub(),
        "transformers": _check_transformers(),
        "torch": _check_torch(),
        "datasets": _check_datasets_lib(),
        "pillow": _check_pillow(),
    }


def _check_pillow() -> bool:
    try:
        from PIL import Image  # noqa
        return True
    except ImportError:
        return False


# ──────────────────────────────────────────────────────────────
# Tải model từ HuggingFace Hub
# ──────────────────────────────────────────────────────────────

def download_model_hf(
    model_id: str,
    model_name: str,
    save_dir: Optional[Path] = None,
    token: Optional[str] = None,
    force: bool = False,
    verbose: bool = True,
) -> Tuple[bool, str]:
    """
    Tải model từ HuggingFace Hub về local.

    Args:
        model_id  : HuggingFace model ID (e.g. "dima806/facial_emotions_image_detection")
        model_name: Tên local để lưu và track
        save_dir  : Thư mục lưu (mặc định HF_MODELS_DIR / model_name)
        token     : HF API token (cần cho private models)
        force     : Tải lại dù đã tồn tại
        verbose   : In tiến trình

    Returns:
        (success: bool, save_path: str)
    """
    if save_dir is None:
        save_dir = HF_MODELS_DIR / model_name.replace("/", "_")

    save_path = str(save_dir)

    if not force and _is_downloaded(model_name):
        if verbose:
            print(f"  ✓ [{model_name}] Đã tải – bỏ qua (dùng force=True để tải lại)")
        return True, save_path

    if not _check_huggingface_hub():
        return False, "huggingface_hub chưa được cài. Chạy: pip install huggingface-hub"

    try:
        from huggingface_hub import snapshot_download

        if verbose:
            print(f"  ⬇  Đang tải [{model_id}] → {save_path} ...")

        start = time.time()
        local_dir = snapshot_download(
            repo_id=model_id,
            local_dir=save_path,
            token=token,
            ignore_patterns=["*.msgpack", "flax_model*", "tf_model*",
                             "rust_model*", "*.ot", "*.arrow"],
        )
        elapsed = time.time() - start

        _mark_downloaded(model_name, model_id, local_dir)

        size_mb = sum(f.stat().st_size for f in Path(local_dir).rglob("*") if f.is_file()) / 1e6
        if verbose:
            print(f"  ✓ [{model_name}] Tải xong → {local_dir} ({size_mb:.1f} MB, {elapsed:.0f}s)")
        return True, local_dir

    except Exception as e:
        err = f"Lỗi tải [{model_id}]: {e}"
        logger.error(err)
        if verbose:
            print(f"  ✗ {err}")

        # Đánh dấu failed trong status
        status = _load_download_status()
        status[model_name] = {"model_id": model_id, "status": "failed", "error": str(e)}
        _save_download_status(status)
        return False, str(e)


# ──────────────────────────────────────────────────────────────
# Tải tất cả emotion models
# ──────────────────────────────────────────────────────────────

def download_all_emotion_models(
    token: Optional[str] = None,
    force: bool = False,
    primary_only: bool = True,
) -> Dict[str, Any]:
    """
    Tải model nhận dạng cảm xúc từ HuggingFace.

    Args:
        primary_only: True = chỉ tải model ưu tiên 1 (tiết kiệm thời gian)
    """
    results = {}
    models = EMOTION_MODELS if not primary_only else [m for m in EMOTION_MODELS if m["priority"] == 1]

    for model_info in models:
        name = model_info["name"]
        model_id = model_info["model_id"]
        print(f"\n📦 Emotion Model: {name}")
        print(f"   {model_info['description']}")

        ok, path = download_model_hf(
            model_id=model_id,
            model_name=name,
            token=token,
            force=force,
        )
        results[name] = {"success": ok, "path": path, "model_id": model_id}

    return results


# ──────────────────────────────────────────────────────────────
# Tải DAiSEE dataset (ví dụ nhỏ từ HuggingFace)
# ──────────────────────────────────────────────────────────────

def download_sample_dataset(
    dataset_name: str = "engagement_sample",
    max_samples: int = 200,
    token: Optional[str] = None,
    verbose: bool = True,
) -> Tuple[bool, str]:
    """
    Tải dataset mẫu nhỏ từ HuggingFace để test pipeline.
    Dùng dataset engagement/face nhỏ có sẵn trên HF.

    Các lựa chọn:
    - "engagement_sample" : tải sample nhỏ từ phpsworld/student-engagement
    - "fer2013_sample"    : tải sample FER2013 (7 cảm xúc)
    """
    if not _check_datasets_lib():
        return False, "datasets library chưa cài. Chạy: pip install datasets"

    save_path = str(DATASETS_DIR / dataset_name)

    if verbose:
        print(f"\n📊 Tải dataset: {dataset_name} (tối đa {max_samples} mẫu)")

    try:
        from datasets import load_dataset

        if dataset_name == "engagement_sample":
            # Dataset nhỏ về student engagement detection
            ds = load_dataset(
                "phpsworld/student-engagement",
                split=f"train[:{max_samples}]",
                token=token,
                trust_remote_code=True,
            )
            ds.save_to_disk(save_path)

        elif dataset_name == "fer2013_sample":
            # FER2013 - emotion recognition standard benchmark
            ds = load_dataset(
                "EthanBehrends/fer2013-with-images",
                split=f"train[:{max_samples}]",
                token=token,
                trust_remote_code=True,
            )
            ds.save_to_disk(save_path)

        else:
            return False, f"Dataset không được hỗ trợ: {dataset_name}"

        if verbose:
            print(f"  ✓ Dataset lưu tại: {save_path}")
            print(f"  Số mẫu: {len(ds)}")  # type: ignore[arg-type]

        # Cập nhật status
        status = _load_download_status()
        status[f"dataset_{dataset_name}"] = {
            "save_path": save_path,
            "samples": max_samples,
            "status": "ok",
            "downloaded_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        _save_download_status(status)

        return True, save_path

    except Exception as e:
        err = f"Lỗi tải dataset [{dataset_name}]: {e}"
        logger.error(err)
        if verbose:
            print(f"  ✗ {err}")
        return False, err


# ──────────────────────────────────────────────────────────────
# Main download function
# ──────────────────────────────────────────────────────────────

def download_all(
    token: Optional[str] = None,
    force: bool = False,
    include_datasets: bool = True,
    primary_only: bool = True,
) -> Dict[str, Any]:
    """
    Tải tất cả models và datasets cần thiết.

    Args:
        token           : HuggingFace API token (tuỳ chọn)
        force           : Tải lại dù đã có
        include_datasets: Tải sample datasets hay không
        primary_only    : Chỉ tải model ưu tiên 1

    Returns:
        Dict tổng hợp kết quả
    """
    print("\n" + "="*60)
    print("🚀 HuggingFace Model Downloader - Classroom Engagement System")
    print("="*60)

    # Kiểm tra thư viện
    libs = get_library_status()
    print("\n📚 Kiểm tra thư viện:")
    for lib, ok in libs.items():
        icon = "✓" if ok else "✗"
        print(f"  {icon} {lib}")

    missing = [k for k, v in libs.items() if not v]
    if missing:
        print(f"\n⚠️  Thiếu thư viện: {', '.join(missing)}")
        print("   Chạy lệnh để cài:")
        print("   pip install " + " ".join(missing).replace("torch", "torch --index-url https://download.pytorch.org/whl/cpu"))
        if "huggingface_hub" in missing or "transformers" in missing:
            print("   (hoặc chạy: python setup_hf.py --install-deps)")

    results: Dict[str, Any] = {
        "emotion_models": {},
        "datasets": {},
        "library_status": libs,
    }

    # 1. Tải emotion models
    print("\n" + "-"*40)
    print("🎭 Tải Emotion Recognition Models")
    print("-"*40)
    results["emotion_models"] = download_all_emotion_models(
        token=token, force=force, primary_only=primary_only
    )

    # 2. Tải datasets
    if include_datasets:
        print("\n" + "-"*40)
        print("📊 Tải Sample Datasets")
        print("-"*40)
        ok, path = download_sample_dataset(
            "fer2013_sample", max_samples=500, token=token
        )
        results["datasets"]["fer2013_sample"] = {"success": ok, "path": path}

    # Tổng kết
    print("\n" + "="*60)
    success_count = sum(1 for v in results["emotion_models"].values() if v.get("success"))
    total_count   = len(results["emotion_models"])
    print(f"✅ Models tải thành công: {success_count}/{total_count}")
    print(f"📁 Thư mục cache: {MODELS_CACHE_DIR}")
    print("="*60 + "\n")

    return results


# ──────────────────────────────────────────────────────────────
# Xem trạng thái đã tải
# ──────────────────────────────────────────────────────────────

def show_status():
    """In trạng thái các models đã tải."""
    status = _load_download_status()

    print("\n" + "="*60)
    print("📦 Trạng thái Models Cache")
    print("="*60)

    if not status:
        print("  (chưa tải model nào)")
        return

    for name, info in status.items():
        icon = "✓" if info.get("status") == "ok" else "✗"
        path = info.get("save_path", "")
        exists = Path(path).exists() if path else False
        size_txt = ""
        if exists:
            size_mb = sum(
                f.stat().st_size for f in Path(path).rglob("*") if f.is_file()
            ) / 1e6
            size_txt = f" ({size_mb:.1f} MB)"
        print(f"  {icon} {name}: {info.get('model_id', info.get('save_path', ''))}{size_txt}")

    print(f"\n📁 Cache: {MODELS_CACHE_DIR}")
    print("="*60 + "\n")


def clear_cache(model_name: Optional[str] = None):
    """Xoá toàn bộ cache hoặc một model cụ thể."""
    if model_name:
        target = HF_MODELS_DIR / model_name.replace("/", "_")
        if target.exists():
            shutil.rmtree(target)
            print(f"✓ Đã xoá cache: {target}")
        status = _load_download_status()
        status.pop(model_name, None)
        _save_download_status(status)
    else:
        if MODELS_CACHE_DIR.exists():
            shutil.rmtree(MODELS_CACHE_DIR)
            MODELS_CACHE_DIR.mkdir(parents=True)
            print(f"✓ Đã xoá toàn bộ cache: {MODELS_CACHE_DIR}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="HuggingFace Model Downloader")
    parser.add_argument("--token", type=str, default=None, help="HuggingFace API token")
    parser.add_argument("--force", action="store_true", help="Tải lại dù đã có")
    parser.add_argument("--status", action="store_true", help="Xem trạng thái đã tải")
    parser.add_argument("--no-dataset", action="store_true", help="Bỏ qua dataset")
    parser.add_argument("--all-models", action="store_true", help="Tải tất cả models (không chỉ primary)")
    args = parser.parse_args()

    if args.status:
        show_status()
    else:
        download_all(
            token=args.token,
            force=args.force,
            include_datasets=not args.no_dataset,
            primary_only=not args.all_models,
        )
