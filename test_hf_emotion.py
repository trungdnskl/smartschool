import sys, os
sys.path.insert(0, r'E:\New folder (3)\classroom\backend')
os.chdir(r'E:\New folder (3)\classroom\backend')

import numpy as np
from PIL import Image
from transformers import pipeline
import time

model_path = r'E:\New folder (3)\classroom\models_cache\huggingface\facial_emotions_primary'
print('[*] Loading HuggingFace emotion model...')
t0 = time.time()
pipe = pipeline('image-classification', model=model_path, device=-1, top_k=5)
load_time = time.time() - t0

print(f'[OK] Model loaded in {load_time:.1f}s')

# Test inference speed
dummy = Image.fromarray(np.random.randint(0, 200, (224, 224, 3), dtype=np.uint8))
t1 = time.time()
for _ in range(3):
    result = pipe(dummy)
avg_ms = (time.time() - t1) / 3 * 1000

print(f'[OK] Inference: {avg_ms:.0f}ms/image (avg 3 runs)')
print('[OK] Sample output:')
for r in result:
    label = r['label']
    score = r['score']
    print(f'     {label}: {score:.3f}')

print('[OK] HuggingFace emotion engine READY!')

# Test full HFEmotionRecognizer class
print('\n[*] Testing HFEmotionRecognizer class...')
from hf_models.hf_emotion_recognizer import HFEmotionRecognizer
rec = HFEmotionRecognizer()
ok = rec.initialize()
print(f'[{"OK" if ok else "FAIL"}] HFEmotionRecognizer.initialize() = {ok}')

if ok:
    face_bgr = np.random.randint(0, 200, (112, 112, 3), dtype=np.uint8)
    result2 = rec.recognize_emotion(face_bgr, face_id=1)
    print(f'[OK] recognize_emotion output: {result2}')
