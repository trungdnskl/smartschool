"""
Full system integration test
"""
import sys, os
sys.path.insert(0, r'E:\New folder (3)\classroom\backend')
os.chdir(r'E:\New folder (3)\classroom\backend')

import numpy as np

print("=" * 55)
print("Classroom Engagement System - Integration Test")
print("=" * 55)

# 1. Test HuggingFace Emotion Engine
print("\n[1] HuggingFace Emotion Recognizer")
try:
    from hf_models.hf_emotion_recognizer import HFEmotionRecognizer
    rec = HFEmotionRecognizer()
    ok = rec.initialize()
    face = np.random.randint(50, 200, (112, 112, 3), dtype=np.uint8)
    result = rec.recognize_emotion(face, face_id=1)
    emotion = result.get('emotion', '?')
    score = result.get('emotion_score', 0)
    engine = result.get('engine', '?')
    print(f"  [OK] Engine: {engine}")
    print(f"  [OK] Result: emotion={emotion}, score={score}")
except Exception as e:
    print(f"  [FAIL] {e}")

# 2. Test EmotionRecognizer wrapper (dual-engine)
print("\n[2] EmotionRecognizer (dual-engine wrapper)")
try:
    from emotion_recognizer import EmotionRecognizer
    er = EmotionRecognizer()
    er.initialize()
    face = np.random.randint(50, 200, (112, 112, 3), dtype=np.uint8)
    result = er.recognize_emotion(face, face_id=2)
    engine = result.get('engine', '?')
    emotion = result.get('emotion', '?')
    print(f"  [OK] Active engine: {er._active_engine}")
    print(f"  [OK] Result: emotion={emotion}, engine={engine}")
except Exception as e:
    print(f"  [FAIL] {e}")

# 3. Test InsightFace ONNX (direct)
print("\n[3] InsightFace ONNX Recognizer (no Visual C++ needed)")
try:
    from hf_models.insightface_recognizer import InsightFaceRecognizer
    ifr = InsightFaceRecognizer()
    ok = ifr.initialize()
    stats = ifr.get_stats()
    print(f"  [{'OK' if ok else 'WARN'}] Model available: {ok}")
    print(f"  [INFO] Stats: {stats}")
except Exception as e:
    print(f"  [INFO] InsightFace ONNX: {e}")
    print(f"  [INFO] Will use DeepFace/LBPH fallback")

# 4. Test AttendanceTracker engine selection
print("\n[4] AttendanceTracker - engine cascade")
try:
    from attendance_tracker import AttendanceTracker
    at = AttendanceTracker()
    at.initialize()
    engine = at._deep_engine_name if at._use_deep else 'lbph'
    print(f"  [OK] Active engine: {engine} (use_deep={at._use_deep})")
    print(f"  [OK] LBPH trained: {at._recognizer_trained}")
except Exception as e:
    print(f"  [FAIL] {e}")

print("\n" + "=" * 55)
print("Test complete. Check [OK]/[FAIL] statuses above.")
print("=" * 55)
