"""
=============================================================
  Classroom Engagement System — Model Setup Script
=============================================================
Cài đặt dependencies và tải models từ HuggingFace/InsightFace.

Chạy 1 lần trước khi khởi động hệ thống:
    python setup_models.py

Options:
    --check-only     Kiểm tra môi trường, không cài gì
    --install-deps   Cài packages thiếu tự động (pip)
    --force          Tải lại models dù đã có
    --token TOKEN    HuggingFace API token (nếu cần)
=============================================================
"""

import sys
import os
import subprocess
import json
import time
import shutil
import argparse
from pathlib import Path

# ──────────────────────────────────────────────────────────────
# Đường dẫn project
# ──────────────────────────────────────────────────────────────
PROJECT_DIR   = Path(__file__).parent
BACKEND_DIR   = PROJECT_DIR / "backend"
MODELS_CACHE  = PROJECT_DIR / "models_cache"
HF_CACHE_DIR  = MODELS_CACHE / "huggingface"
INSIGHT_DIR   = MODELS_CACHE / "insightface"
STATUS_FILE   = MODELS_CACHE / "setup_status.json"

for _d in [MODELS_CACHE, HF_CACHE_DIR, INSIGHT_DIR]:
    _d.mkdir(parents=True, exist_ok=True)


# ──────────────────────────────────────────────────────────────
# ANSI Colors (Windows-compatible)
# ──────────────────────────────────────────────────────────────
def _supports_color() -> bool:
    return sys.stdout.isatty() and os.name != "nt" or os.environ.get("TERM_PROGRAM") == "vscode"

C_OK    = "\033[92m" if _supports_color() else ""
C_WARN  = "\033[93m" if _supports_color() else ""
C_ERR   = "\033[91m" if _supports_color() else ""
C_INFO  = "\033[94m" if _supports_color() else ""
C_BOLD  = "\033[1m"  if _supports_color() else ""
C_RESET = "\033[0m"  if _supports_color() else ""

def ok(msg):   print(f"  {C_OK}✓{C_RESET} {msg}")
def warn(msg): print(f"  {C_WARN}⚠{C_RESET}  {msg}")
def err(msg):  print(f"  {C_ERR}✗{C_RESET} {msg}")
def info(msg): print(f"  {C_INFO}→{C_RESET} {msg}")
def header(msg): print(f"\n{C_BOLD}{msg}{C_RESET}")


# ──────────────────────────────────────────────────────────────
# Status tracking
# ──────────────────────────────────────────────────────────────

def _load_status() -> dict:
    if STATUS_FILE.exists():
        try:
            return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_status(status: dict):
    STATUS_FILE.write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")


def _mark_done(key: str, info_dict: dict = None):
    s = _load_status()
    s[key] = {"status": "ok", "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), **(info_dict or {})}
    _save_status(s)


def _is_done(key: str, check_path: str = None) -> bool:
    s = _load_status()
    entry = s.get(key, {})
    if entry.get("status") != "ok":
        return False
    if check_path:
        return Path(check_path).exists()
    return True


# ──────────────────────────────────────────────────────────────
# Package checking & installation
# ──────────────────────────────────────────────────────────────

REQUIRED_PACKAGES = {
    # package_name_to_import : (pip_install_name, display_name, critical)
    "onnxruntime":        ("onnxruntime",                 "ONNX Runtime (CPU)",          True),
    "insightface":        ("insightface",                  "InsightFace (ArcFace)",        True),
    "huggingface_hub":    ("huggingface-hub",              "HuggingFace Hub",             True),
    "transformers":       ("transformers",                 "Transformers (HF)",           True),
    "torch":              ("torch --index-url https://download.pytorch.org/whl/cpu",
                                                           "PyTorch (CPU)",               True),
    "PIL":                ("Pillow",                       "Pillow (imaging)",            True),
    "timm":               ("timm",                         "timm (ViT models)",           False),
    "datasets":           ("datasets",                     "HuggingFace Datasets",       False),
    "scipy":              ("scipy",                        "SciPy",                       False),
    "sklearn":            ("scikit-learn",                 "scikit-learn",               False),
}


def check_package(import_name: str) -> bool:
    """Try to import a package, return True if available."""
    try:
        __import__(import_name)
        return True
    except ImportError:
        return False


def install_package(pip_name: str, display_name: str) -> bool:
    """Install a pip package. Returns True on success."""
    print(f"\n  📦 Cài {display_name} ...")
    try:
        parts = [sys.executable, "-m", "pip", "install"] + pip_name.split()
        result = subprocess.run(parts, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            ok(f"{display_name} đã cài xong")
            return True
        else:
            err(f"Cài {display_name} thất bại:\n{result.stderr[-500:]}")
            return False
    except subprocess.TimeoutExpired:
        err(f"Timeout khi cài {display_name}")
        return False
    except Exception as e:
        err(f"Lỗi khi cài {display_name}: {e}")
        return False


def check_and_install_deps(auto_install: bool = False) -> dict:
    """Check all required packages, optionally install missing ones."""
    header("📦 Kiểm tra Dependencies")
    results = {}

    for import_name, (pip_name, display_name, critical) in REQUIRED_PACKAGES.items():
        available = check_package(import_name)

        if available:
            ok(f"{display_name}")
            results[import_name] = True
        else:
            (warn if not critical else err)(f"{display_name} — CHƯA CÀI")
            results[import_name] = False

            if auto_install:
                success = install_package(pip_name, display_name)
                if success:
                    results[import_name] = check_package(import_name)
            else:
                if critical:
                    info(f"Cài: pip install {pip_name.split()[0]}")

    return results


# ──────────────────────────────────────────────────────────────
# InsightFace buffalo_l model download
# ──────────────────────────────────────────────────────────────

def download_insightface_model(force: bool = False) -> bool:
    """
    Tải InsightFace buffalo_l model về local.
    InsightFace tự quản lý cache trong ~/.insightface/models/
    Chúng ta trigger download bằng cách khởi tạo FaceAnalysis.
    """
    header("🔍 InsightFace ArcFace Model (buffalo_l)")

    model_dir = Path.home() / ".insightface" / "models" / "buffalo_l"
    local_symlink = INSIGHT_DIR / "buffalo_l"

    if not force and (model_dir.exists() or local_symlink.exists()):
        ok("buffalo_l đã có (bỏ qua)")
        return True

    if not check_package("insightface"):
        err("insightface chưa cài — bỏ qua download")
        return False

    info("Đang tải buffalo_l (~300 MB)...")
    print("    (Lần đầu chạy, tải ~5-10 phút tuỳ tốc độ mạng)\n")

    try:
        import insightface
        from insightface.app import FaceAnalysis

        # Trigger download bằng cách khởi tạo model
        app = FaceAnalysis(
            name="buffalo_l",
            root=str(INSIGHT_DIR),
            providers=["CPUExecutionProvider"],
        )
        app.prepare(ctx_id=-1, det_size=(640, 640))  # ctx_id=-1 = CPU

        ok(f"buffalo_l tải xong → {INSIGHT_DIR / 'models' / 'buffalo_l'}")
        _mark_done("insightface_buffalo_l", {"model_path": str(INSIGHT_DIR / "models" / "buffalo_l")})
        return True

    except Exception as e:
        err(f"Lỗi tải buffalo_l: {e}")
        warn("Hệ thống sẽ dùng DeepFace làm fallback")
        return False


# ──────────────────────────────────────────────────────────────
# HuggingFace emotion model download
# ──────────────────────────────────────────────────────────────

# Model được chọn: dima806/facial_emotions_image_detection
# - 27MB, MobileNet-based, accuracy 93% trên FER2013
# - CPU inference ~30ms/image (sau khi tối ưu với ONNX pipeline)
EMOTION_MODEL_ID   = "dima806/facial_emotions_image_detection"
EMOTION_MODEL_NAME = "facial_emotions_primary"
EMOTION_MODEL_DIR  = HF_CACHE_DIR / EMOTION_MODEL_NAME


def download_hf_emotion_model(token: str = None, force: bool = False) -> bool:
    """Tải emotion recognition model từ HuggingFace."""
    header(f"🎭 Emotion Model: {EMOTION_MODEL_ID}")

    if not force and _is_done("hf_emotion_model", str(EMOTION_MODEL_DIR)):
        ok(f"Emotion model đã có → {EMOTION_MODEL_DIR}")
        return True

    if not check_package("huggingface_hub"):
        err("huggingface_hub chưa cài")
        return False

    info(f"Đang tải {EMOTION_MODEL_ID} (~27 MB)...")

    try:
        from huggingface_hub import snapshot_download

        local_dir = snapshot_download(
            repo_id=EMOTION_MODEL_ID,
            local_dir=str(EMOTION_MODEL_DIR),
            token=token,
            ignore_patterns=[
                "*.msgpack", "flax_model*", "tf_model*",
                "rust_model*", "*.ot", "*.arrow", "*.parquet",
                "runs/*", ".git/*",
            ],
        )

        # Tính size
        size_mb = sum(
            f.stat().st_size for f in Path(local_dir).rglob("*") if f.is_file()
        ) / 1e6

        ok(f"Emotion model → {local_dir} ({size_mb:.1f} MB)")
        _mark_done("hf_emotion_model", {"path": local_dir, "model_id": EMOTION_MODEL_ID})
        return True

    except Exception as e:
        err(f"Lỗi tải emotion model: {e}")
        if "401" in str(e) or "403" in str(e):
            warn("Model có thể cần HF token. Tạo token tại: https://huggingface.co/settings/tokens")
            warn("Chạy lại: python setup_models.py --token YOUR_TOKEN")
        warn("Hệ thống sẽ dùng FER library làm fallback emotion")
        return False


# ──────────────────────────────────────────────────────────────
# Verify models work
# ──────────────────────────────────────────────────────────────

def verify_insightface() -> bool:
    """Verify InsightFace model loads correctly."""
    header("🔬 Verify InsightFace")
    try:
        import numpy as np
        from insightface.app import FaceAnalysis

        app = FaceAnalysis(
            name="buffalo_l",
            root=str(INSIGHT_DIR),
            providers=["CPUExecutionProvider"],
        )
        app.prepare(ctx_id=-1, det_size=(320, 320))

        # Test với fake image
        dummy = np.zeros((112, 112, 3), dtype=np.uint8)
        result = app.get(dummy)
        ok(f"InsightFace hoạt động bình thường (faces detected on dummy: {len(result)})")
        return True
    except Exception as e:
        err(f"InsightFace verify thất bại: {e}")
        return False


def verify_hf_emotion_model() -> bool:
    """Verify HF emotion model loads and runs."""
    header("🔬 Verify Emotion Model")
    try:
        import numpy as np
        from PIL import Image
        from transformers import pipeline

        model_path = str(EMOTION_MODEL_DIR)
        if not EMOTION_MODEL_DIR.exists():
            err("Emotion model chưa được tải")
            return False

        info("Đang load emotion model (lần đầu ~5–10 giây)...")
        pipe = pipeline(
            "image-classification",
            model=model_path,
            device=-1,  # CPU
        )

        # Test với PIL image 224x224
        dummy_img = Image.fromarray(
            np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)
        )
        result = pipe(dummy_img, top_k=3)
        labels = [r["label"] for r in result]
        ok(f"Emotion model hoạt động. Output labels: {labels}")
        return True

    except Exception as e:
        err(f"Emotion model verify thất bại: {e}")
        return False


# ──────────────────────────────────────────────────────────────
# Write config file for backend
# ──────────────────────────────────────────────────────────────

def write_model_config():
    """Ghi config file cho backend biết paths của models."""
    config = {
        "version": "2.0",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),

        "face_recognition": {
            "engine": "insightface",                          # primary
            "fallback": "deepface",                           # fallback
            "insightface": {
                "model_name": "buffalo_l",
                "model_root": str(INSIGHT_DIR),
                "det_size": [640, 640],
                "threshold": 0.45,
                "providers": ["CPUExecutionProvider"],
            },
            "deepface": {
                "model_name": "ArcFace",
                "detector_backend": "skip",
                "threshold": 0.45,
            },
        },

        "emotion_recognition": {
            "engine": "huggingface",                          # primary
            "fallback": "fer",                                # fallback
            "huggingface": {
                "model_id": EMOTION_MODEL_ID,
                "model_path": str(EMOTION_MODEL_DIR),
                "task": "image-classification",
                "device": -1,                                 # -1 = CPU
                "input_size": 224,
                "update_interval": 2.0,                       # seconds per face
                "window_size": 5,                             # smoothing frames
                "top_k": 3,
            },
            "fer": {
                "mtcnn": False,
                "update_interval": 2.0,
            },
        },

        "paths": {
            "models_cache": str(MODELS_CACHE),
            "hf_cache": str(HF_CACHE_DIR),
            "insightface_root": str(INSIGHT_DIR),
            "embeddings_dir": str(PROJECT_DIR / "data" / "face_embeddings"),
        },
    }

    config_path = PROJECT_DIR / "backend" / "model_config.json"
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    ok(f"Config ghi vào: {config_path}")
    return config_path


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────

def print_banner():
    print(f"""
{C_BOLD}{'='*58}
  Classroom Engagement System — Model Setup v2.0
  InsightFace ArcFace + HuggingFace Emotion
{'='*58}{C_RESET}""")


def print_summary(results: dict):
    header("📋 Tổng kết")

    face_ok    = results.get("insightface", False)
    emotion_ok = results.get("emotion", False)

    print(f"""
  Face Recognition   : {'✓ InsightFace ArcFace (buffalo_l)' if face_ok else '⚠ DeepFace fallback'}
  Emotion Recognition: {'✓ HuggingFace MobileNet' if emotion_ok else '⚠ FER library fallback'}

  Hệ thống {'SẴN SÀNG' if face_ok or emotion_ok else 'ở chế độ FALLBACK'}. Khởi động bằng:

    cd backend
    python main.py
""")
    if not face_ok:
        warn("InsightFace chưa cài → cài bằng: pip install insightface onnxruntime")
    if not emotion_ok:
        warn("HF emotion model chưa tải → chạy: python setup_models.py --install-deps")


def main():
    parser = argparse.ArgumentParser(description="Classroom Engagement — Model Setup")
    parser.add_argument("--check-only",    action="store_true", help="Kiểm tra thôi, không cài")
    parser.add_argument("--install-deps",  action="store_true", help="Cài packages tự động")
    parser.add_argument("--force",         action="store_true", help="Tải lại models")
    parser.add_argument("--token",         type=str, default=None, help="HuggingFace API token")
    parser.add_argument("--skip-verify",   action="store_true", help="Bỏ qua bước verify")
    parser.add_argument("--skip-dataset",  action="store_true", help="Bỏ qua tải dataset")
    args = parser.parse_args()

    print_banner()

    # 1. Check/install dependencies
    dep_results = check_and_install_deps(auto_install=args.install_deps)

    if args.check_only:
        missing_critical = [
            name for name, avail in dep_results.items()
            if not avail and REQUIRED_PACKAGES[name][2]
        ]
        if missing_critical:
            print(f"\n  Chạy lại với --install-deps để cài tự động:")
            print(f"  python setup_models.py --install-deps\n")
        else:
            ok("Tất cả dependencies đã có!")
        return

    results = {}

    # 2. Download InsightFace model
    results["insightface"] = download_insightface_model(force=args.force)

    # 3. Download HuggingFace emotion model
    results["emotion"] = download_hf_emotion_model(
        token=args.token, force=args.force
    )

    # 4. Verify models
    if not args.skip_verify:
        header("🧪 Verification")
        if results["insightface"] and dep_results.get("insightface"):
            verify_insightface()
        if results["emotion"] and dep_results.get("transformers"):
            verify_hf_emotion_model()

    # 5. Write config for backend
    header("⚙️  Ghi Config")
    write_model_config()

    # 6. Summary
    print_summary(results)


if __name__ == "__main__":
    main()
