"""
test_face_accuracy.py — Đánh giá chính xác độ nhận diện khuôn mặt
=================================================================
Kiểm tra toàn bộ pipeline:
  1. Face Detection: SSD DNN có detect được khuôn mặt trong ảnh không?
  2. LBPH Recognition: Có nhận đúng student không? Confidence bao nhiêu?
  3. InsightFace/ArcFace: Engine nào đang active?
  4. Preprocessing quality: CLAHE, resize, augmentation có đúng không?
"""

import sys
import os
import cv2
import numpy as np
import json
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))
os.chdir(str(Path(__file__).parent))

from face_detector import FaceDetector
from attendance_tracker import AttendanceTracker
from config import get_config


def color(text, code):
    return f"\033[{code}m{text}\033[0m"

def green(t): return color(t, 32)
def red(t): return color(t, 31)
def yellow(t): return color(t, 33)
def cyan(t): return color(t, 36)
def bold(t): return color(t, 1)


def test_face_detection():
    """Test 1: Face Detection — SSD DNN model."""
    print(f"\n{'='*60}")
    print(bold("  TEST 1: Face Detection (OpenCV SSD DNN)"))
    print(f"{'='*60}")
    
    detector = FaceDetector(model_type="opencv_dnn", confidence_threshold=0.6)
    detector.initialize()
    
    # Test with webcam frame (if available)
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print(yellow("  ⚠ Không mở được webcam (USB camera) — bỏ qua test live"))
        print("  Thử với ảnh synthetic...")
        # Create synthetic test image
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        img[100:300, 200:400] = 180  # Gray rectangle as "face area"
        faces = detector.detect_faces(img)
        print(f"  Synthetic image: {len(faces)} faces detected (expected: 0-1)")
        return detector
    
    results = []
    for i in range(10):
        ret, frame = cap.read()
        if not ret:
            break
        t0 = time.time()
        faces = detector.detect_faces(frame)
        dt = (time.time() - t0) * 1000
        results.append({"faces": len(faces), "time_ms": dt, "details": faces})
        
    cap.release()
    
    total_frames = len(results)
    frames_with_faces = sum(1 for r in results if r["faces"] > 0)
    avg_time = sum(r["time_ms"] for r in results) / max(total_frames, 1)
    
    print(f"\n  📊 Kết quả Detection ({total_frames} frames):")
    print(f"  {'─'*50}")
    print(f"  Frames có khuôn mặt : {frames_with_faces}/{total_frames} ({frames_with_faces/max(total_frames,1)*100:.0f}%)")
    print(f"  Thời gian trung bình: {avg_time:.1f}ms/frame")
    
    if results and results[-1]["faces"] > 0:
        last = results[-1]["details"][0]
        print(f"  Confidence cuối     : {last['confidence']:.3f}")
        bbox = last["bbox"]
        print(f"  Bounding box        : ({bbox[0]},{bbox[1]}) → ({bbox[2]},{bbox[3]})")
        w, h = bbox[2]-bbox[0], bbox[3]-bbox[1]
        print(f"  Kích thước khuôn mặt: {w}x{h} pixels")
    
    if frames_with_faces == 0:
        print(red("  ❌ FAIL — Không detect được khuôn mặt nào!"))
    elif frames_with_faces >= total_frames * 0.5:
        print(green(f"  ✅ PASS — Detection ổn định ({frames_with_faces}/{total_frames})"))
    else:
        print(yellow(f"  ⚠ WARN — Detection không ổn định ({frames_with_faces}/{total_frames})"))
    
    return detector


def test_enrollment_data():
    """Test 2: Kiểm tra dữ liệu enrollment."""
    print(f"\n{'='*60}")
    print(bold("  TEST 2: Kiểm tra dữ liệu Enrollment"))
    print(f"{'='*60}")
    
    emb_dir = Path(__file__).parent.parent / "data" / "face_embeddings"
    deep_pkl = emb_dir / "deep_embeddings.pkl"
    
    # LBPH data
    lbph_students = []
    for d in emb_dir.iterdir():
        if d.is_dir():
            meta = d / "metadata.json"
            if meta.exists():
                m = json.loads(meta.read_text(encoding="utf-8"))
                samples = list(d.glob("sample_*.png"))
                lbph_students.append({
                    "id": m["student_id"],
                    "name": m["name"],
                    "samples": len(samples),
                    "class": m.get("class_name", ""),
                })
    
    print(f"\n  📋 LBPH Students: {len(lbph_students)}")
    print(f"  {'─'*50}")
    
    issues = []
    for s in lbph_students:
        status = "✅" if s["samples"] >= 6 else "⚠"
        print(f"  {status} {s['name']} (ID: {s['id']}) — {s['samples']} samples")
        
        if s["samples"] < 4:
            issues.append(f"  {s['name']}: Quá ít samples ({s['samples']}). Cần ít nhất 6 (1 ảnh gốc × 6 augmented)")
        
        # Check sample quality
        sample_dir = emb_dir / s["id"]
        for img_file in sorted(sample_dir.glob("sample_*.png"))[:1]:
            img = cv2.imread(str(img_file), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                mean_val = np.mean(img)
                std_val = np.std(img)
                h, w = img.shape
                print(f"      Size: {w}x{h}, Mean: {mean_val:.1f}, Std: {std_val:.1f}")
                if std_val < 20:
                    issues.append(f"  {s['name']}: Ảnh quá đồng nhất (std={std_val:.1f}), có thể bị lỗi preprocessing")
                if mean_val < 30 or mean_val > 230:
                    issues.append(f"  {s['name']}: Ảnh quá tối/sáng (mean={mean_val:.1f})")
    
    # Deep embeddings
    print(f"\n  📋 Deep Embeddings (ArcFace/InsightFace):")
    print(f"  {'─'*50}")
    if deep_pkl.exists():
        import pickle
        with open(deep_pkl, "rb") as f:
            data = pickle.load(f)
        students = data.get("students", {}) if isinstance(data, dict) else data
        model = data.get("model", "unknown") if isinstance(data, dict) else "unknown"
        threshold = data.get("threshold_recommended", "?") if isinstance(data, dict) else "?"
        print(f"  Model     : {model}")
        print(f"  Threshold : {threshold}")
        print(f"  Students  : {len(students)}")
        for sid, sdata in students.items():
            name = sdata.get("name", sid) if isinstance(sdata, dict) else sid
            emb_count = len(sdata.get("embeddings", [])) if isinstance(sdata, dict) else len(sdata)
            source = sdata.get("source", "?") if isinstance(sdata, dict) else "?"
            print(f"    ✅ {name}: {emb_count} embeddings (source: {source})")
        print(green("  ✅ Deep engine data available"))
    else:
        print(red("  ❌ deep_embeddings.pkl KHÔNG TỒN TẠI"))
        print(yellow("  → ArcFace/InsightFace sẽ KHÔNG hoạt động"))
        print(yellow("  → Hệ thống chỉ dùng LBPH (accuracy ~75-85%)"))
        issues.append("Deep embeddings chưa có — cần enroll students qua dashboard hoặc import từ Colab")
    
    if issues:
        print(f"\n  ⚠ Vấn đề phát hiện:")
        for issue in issues:
            print(yellow(f"  {issue}"))
    
    return lbph_students, deep_pkl.exists()


def test_lbph_recognition():
    """Test 3: LBPH Recognition accuracy."""
    print(f"\n{'='*60}")
    print(bold("  TEST 3: LBPH Recognition Accuracy"))
    print(f"{'='*60}")
    
    cfg = get_config()
    tracker = AttendanceTracker(
        match_threshold=cfg.attendance.match_threshold,
        deep_face_threshold=cfg.attendance.deep_face_threshold,
        check_interval=0,  # No rate limiting for test
    )
    tracker.initialize()
    
    print(f"\n  Engine active  : {'InsightFace/ArcFace' if tracker._use_deep else 'LBPH (fallback)'}")
    print(f"  Deep engine    : {tracker._deep_engine_name}")
    print(f"  LBPH trained   : {tracker._recognizer_trained}")
    print(f"  LBPH students  : {len(tracker._enrolled_faces)}")
    print(f"  Match threshold: {tracker.match_threshold}")
    
    if not tracker._recognizer_trained:
        print(red("  ❌ LBPH chưa trained — không thể test recognition"))
        return
    
    # Self-recognition test: Use enrolled samples to test
    print(f"\n  📊 Self-Recognition Test (enrolled samples):")
    print(f"  {'─'*50}")
    
    emb_dir = Path(__file__).parent.parent / "data" / "face_embeddings"
    total_tests = 0
    correct = 0
    wrong = 0
    no_match = 0
    
    for student_id, data in tracker._enrolled_faces.items():
        name = data["name"]
        samples = data.get("samples", [])
        
        if not samples:
            continue
        
        student_correct = 0
        student_total = 0
        scores = []
        
        for i, sample in enumerate(samples[:3]):  # Test first 3 samples
            if sample is None or sample.size == 0:
                continue
            
            # LBPH predict
            label, confidence = tracker._face_recognizer.predict(sample)
            similarity = max(0, 1.0 - (confidence / 200.0))
            predicted_id = tracker._label_to_student.get(label, "unknown")
            
            total_tests += 1
            student_total += 1
            scores.append(similarity)
            
            if predicted_id == student_id and similarity >= tracker.match_threshold:
                correct += 1
                student_correct += 1
            elif predicted_id != student_id:
                wrong += 1
            else:
                no_match += 1
        
        avg_score = sum(scores) / len(scores) if scores else 0
        status = "✅" if student_correct == student_total else ("⚠" if student_correct > 0 else "❌")
        print(f"  {status} {name}: {student_correct}/{student_total} correct, avg score: {avg_score:.3f}")
    
    if total_tests > 0:
        accuracy = correct / total_tests * 100
        print(f"\n  📊 Tổng kết LBPH Self-Test:")
        print(f"  {'─'*50}")
        print(f"  Tổng test    : {total_tests}")
        print(f"  Đúng         : {correct} ({accuracy:.1f}%)")
        print(f"  Sai          : {wrong}")
        print(f"  Không match  : {no_match}")
        
        if accuracy >= 90:
            print(green(f"  ✅ LBPH accuracy TỐT ({accuracy:.1f}%)"))
        elif accuracy >= 70:
            print(yellow(f"  ⚠ LBPH accuracy TRUNG BÌNH ({accuracy:.1f}%)"))
        else:
            print(red(f"  ❌ LBPH accuracy THẤP ({accuracy:.1f}%)"))
    
    return tracker


def test_live_recognition(detector, tracker):
    """Test 4: Live detection + recognition pipeline."""
    print(f"\n{'='*60}")
    print(bold("  TEST 4: Live Detection → Recognition Pipeline"))
    print(f"{'='*60}")
    
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print(yellow("  ⚠ Không mở được webcam — bỏ qua test live"))
        return
    
    print("  Đang chụp 5 frames từ webcam...")
    
    results = []
    for i in range(5):
        ret, frame = cap.read()
        if not ret:
            break
        time.sleep(0.3)  # Small delay between frames
        
        # Detect
        faces = detector.detect_faces(frame)
        
        for face in faces:
            face_crop = detector.crop_face(frame, face["bbox"], margin=0.1)
            if face_crop is None:
                continue
            
            # Preprocess
            gray = tracker._preprocess_face(face_crop)
            if gray is None:
                continue
            
            # LBPH predict
            if tracker._recognizer_trained and tracker._face_recognizer is not None:
                label, confidence = tracker._face_recognizer.predict(gray)
                similarity = max(0, 1.0 - (confidence / 200.0))
                predicted_id = tracker._label_to_student.get(label, "unknown")
                predicted_name = tracker._enrolled_faces.get(predicted_id, {}).get("name", "?")
                
                results.append({
                    "frame": i,
                    "predicted": predicted_name,
                    "predicted_id": predicted_id,
                    "similarity": similarity,
                    "confidence_raw": confidence,
                    "match": similarity >= tracker.match_threshold,
                })
    
    cap.release()
    
    if not results:
        print(yellow("  ⚠ Không detect được khuôn mặt nào trong 5 frames"))
        return
    
    print(f"\n  📊 Live Recognition Results:")
    print(f"  {'─'*60}")
    print(f"  {'Frame':<8} {'Predicted':<18} {'Similarity':<12} {'Match'}")
    print(f"  {'─'*60}")
    
    for r in results:
        match_str = green("✅ YES") if r["match"] else red("❌ NO")
        sim_color = green if r["similarity"] >= 0.6 else (yellow if r["similarity"] >= 0.4 else red)
        sim_str = f"{r['similarity']:.3f}"
        print(f"  {r['frame']:<8} {r['predicted']:<18} {sim_color(sim_str):<12} {match_str}")
    
    # Summary
    matched = sum(1 for r in results if r["match"])
    avg_sim = sum(r["similarity"] for r in results) / len(results)
    print(f"\n  Matched: {matched}/{len(results)}, Avg similarity: {avg_sim:.3f}")
    
    if avg_sim < 0.4:
        print(red("  ⚠ Similarity rất thấp — người trước camera có thể không phải student đã enroll"))
    elif avg_sim < tracker.match_threshold:
        print(yellow("  ⚠ Similarity dưới threshold — cần thêm samples hoặc điều chỉnh threshold"))


def test_engine_status():
    """Test 5: Engine status summary."""
    print(f"\n{'='*60}")
    print(bold("  TEST 5: Engine Status & Recommendations"))
    print(f"{'='*60}")
    
    cfg = get_config()
    tracker = AttendanceTracker(
        match_threshold=cfg.attendance.match_threshold,
        deep_face_threshold=cfg.attendance.deep_face_threshold,
    )
    tracker.initialize()
    
    # Engine cascade status
    print(f"\n  📋 Engine Cascade:")
    print(f"  {'─'*50}")
    
    # Tier 1: InsightFace
    if tracker._deep_engine_name == "insightface":
        if tracker._use_deep:
            print(green("  ✅ Tier 1: InsightFace ONNX — ACTIVE"))
        else:
            print(yellow("  ⚠ Tier 1: InsightFace ONNX — Loaded nhưng chưa có embeddings"))
    else:
        print(red("  ❌ Tier 1: InsightFace — Không khả dụng"))
    
    # Tier 2: DeepFace
    if tracker._deep_engine_name == "deepface":
        if tracker._use_deep:
            print(green("  ✅ Tier 2: DeepFace (ArcFace) — ACTIVE"))
        else:
            print(yellow("  ⚠ Tier 2: DeepFace — Loaded nhưng chưa có embeddings"))
    else:
        print("  ⏭ Tier 2: DeepFace — Skipped (InsightFace available)")
    
    # Tier 3: LBPH
    if tracker._recognizer_trained:
        print(green(f"  ✅ Tier 3: LBPH — Trained ({len(tracker._enrolled_faces)} students)"))
    else:
        print(red("  ❌ Tier 3: LBPH — Chưa trained"))
    
    # Active engine
    print(f"\n  🔄 Active Engine: ", end="")
    if tracker._use_deep:
        print(green(f"{tracker._deep_engine_name.upper()} (Deep Learning) — Accuracy: ~94-99%"))
    elif tracker._recognizer_trained:
        print(yellow("LBPH (OpenCV) — Accuracy: ~75-85%"))
    else:
        print(red("NONE — Chưa có engine nào sẵn sàng!"))
    
    # Recommendations
    print(f"\n  💡 Khuyến nghị cải thiện:")
    print(f"  {'─'*50}")
    
    deep_exists = (Path(__file__).parent.parent / "data" / "face_embeddings" / "deep_embeddings.pkl").exists()
    
    if not deep_exists:
        print(yellow("  1. [QUAN TRỌNG] Tạo deep embeddings:"))
        print("     → Cách 1: Enroll students qua Dashboard (Settings > Students > Camera)")
        print("     → Cách 2: Chạy Google Colab notebook với ảnh students")
        print("     → File output: data/face_embeddings/deep_embeddings.pkl")
        print()
    
    lbph_count = len(tracker._enrolled_faces)
    for sid, data in tracker._enrolled_faces.items():
        samples = len(data.get("samples", []))
        if samples < 12:
            print(yellow(f"  2. {data['name']}: Chỉ có {samples} LBPH samples."))
            print(f"     → Enroll thêm 2-3 ảnh từ góc khác nhau (sẽ tăng lên ~18-20 samples)")
    
    if lbph_count < 3:
        print(yellow(f"  3. Chỉ có {lbph_count} students. Hệ thống cần nhiều students hơn để test chính xác."))
    
    if not tracker._use_deep and tracker._deep_engine_name == "insightface":
        print(cyan("  4. InsightFace ONNX đã load nhưng thiếu embeddings."))
        print("     → Sau khi enroll students, hệ thống sẽ tự kích hoạt ArcFace (~94-99%)")
    
    print(green("\n  5. Để đạt accuracy tốt nhất:"))
    print("     → Mỗi student cần 3-5 ảnh gốc (khác góc, khác ánh sáng)")
    print("     → Camera đặt ngang tầm mắt, đủ sáng")
    print("     → Khoảng cách: 0.5-3m cho khuôn mặt rõ ràng")


if __name__ == "__main__":
    print(bold("\n" + "="*60))
    print(bold("  🔍 FACE RECOGNITION ACCURACY REPORT"))
    print(bold("  Classroom Engagement System (NEHS)"))
    print(bold("="*60))
    
    # Test 1: Detection
    detector = test_face_detection()
    
    # Test 2: Enrollment data
    lbph_students, has_deep = test_enrollment_data()
    
    # Test 3: LBPH accuracy
    tracker = test_lbph_recognition()
    
    # Test 4: Live pipeline (if webcam available)
    if detector and tracker:
        test_live_recognition(detector, tracker)
    
    # Test 5: Engine summary
    test_engine_status()
    
    print(f"\n{'='*60}")
    print(bold("  📊 REPORT COMPLETE"))
    print(f"{'='*60}\n")
