"""Diagnostic test: check InsightFace embedding quality."""
import sys, os, cv2, time, numpy as np
sys.path.insert(0, os.path.dirname(__file__))

from hf_models.insightface_recognizer import InsightFaceRecognizer

rec = InsightFaceRecognizer(threshold=0.30)
rec.initialize()

print(f"Model: {rec._model_available}, DB: {len(rec._db)} students")

# Check stored embeddings
for sid, data in rec._db.items():
    if isinstance(data, dict):
        embs = data.get('embeddings', [])
        centroid = data.get('centroid')
        print(f"\n  {data.get('name')} ({sid}): {len(embs)} embeddings")
        if centroid is not None:
            print(f"  Centroid norm: {np.linalg.norm(centroid):.4f}")
            print(f"  Centroid[:5]: {centroid[:5]}")
        for i, e in enumerate(embs[:3]):
            print(f"  Emb[{i}] norm={np.linalg.norm(e):.4f}, [:5]={e[:5]}")

# Webcam test  
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("\nERROR: Webcam busy")
    sys.exit(1)

# Wait for webcam to warm up
for _ in range(5):
    cap.read()

ret, frame = cap.read()
if ret:
    print(f"\nFrame shape: {frame.shape}")
    
    # Test 1: Full frame embedding
    emb_full = rec.get_face_embedding(frame)
    if emb_full is not None:
        print(f"Full frame embedding: norm={np.linalg.norm(emb_full):.4f}, [:5]={emb_full[:5]}")
    else:
        print("Full frame embedding: NONE (expected if no face crop)")
    
    # Test 2: Use face_detector to get proper crop
    try:
        from face_detector import FaceDetector
        fd = FaceDetector(model_type="mediapipe", confidence_threshold=0.5)
        fd.initialize()
        faces = fd.detect_faces(frame)
        print(f"\nFace detector found: {len(faces)} faces")
        
        for face in faces:
            bbox = face["bbox"]
            crop = fd.crop_face(frame, bbox, margin=0.1)
            if crop is not None:
                print(f"  Face crop shape: {crop.shape}")
                emb_crop = rec.get_face_embedding(crop)
                if emb_crop is not None:
                    print(f"  Crop embedding: norm={np.linalg.norm(emb_crop):.4f}")
                    
                    # Compare with each student
                    for sid, data in rec._db.items():
                        if isinstance(data, dict):
                            centroid = data.get('centroid')
                            if centroid is not None:
                                sim_c = float(np.dot(emb_crop, centroid))
                                print(f"  vs {data.get('name')}: centroid_sim={sim_c:.3f}")
                            embs = data.get('embeddings', [])
                            if embs:
                                sims = [float(np.dot(emb_crop, e)) for e in embs]
                                print(f"    max_emb_sim={max(sims):.3f}, avg={sum(sims)/len(sims):.3f}")
                else:
                    print("  Crop embedding: NONE!")
    except Exception as e:
        print(f"Face detector error: {e}")

cap.release()
print("\nDone!")
