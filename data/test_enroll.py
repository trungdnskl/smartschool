"""
Test script: Enroll students with photos via the API.
Run from classroom/backend directory.
"""
import sys
import os
import requests

BASE_URL = "http://localhost:8001"

students = [
    {
        "student_id": "HS002",
        "name": "Tran Thi Bich",
        "class_name": "10A1",
        "photo": r"e:\New folder (3)\classroom\data\test_images\student_002.jpg",
    },
    {
        "student_id": "HS003",
        "name": "Le Van Cuong",
        "class_name": "10A2",
        "photo": r"e:\New folder (3)\classroom\data\test_images\student_003.jpg",
    },
]

print("=" * 60)
print("  Student Enrollment Test")
print("=" * 60)

for s in students:
    photo_path = s["photo"]
    if not os.path.exists(photo_path):
        print(f"[ERROR] Not found: {photo_path}")
        continue

    with open(photo_path, "rb") as f:
        files = {"photo": (os.path.basename(photo_path), f, "image/jpeg")}
        data = {
            "student_id": s["student_id"],
            "name": s["name"],
            "class_name": s["class_name"],
        }
        r = requests.post(f"{BASE_URL}/api/students/enroll", data=data, files=files)

    if r.status_code == 200:
        j = r.json()
        print(f"  OK  {s['student_id']} {s['name']}")
        print(f"       {j.get('message')}")
        print(f"       sample_count={j.get('sample_count', 0)}")
    else:
        print(f"  FAIL  {s['student_id']} => HTTP {r.status_code}")
        print(f"         {r.text}")

print()

# List all enrolled students
print("=" * 60)
print("  Current Students List")
print("=" * 60)
r = requests.get(f"{BASE_URL}/api/students")
students_data = r.json()
print(f"  Total: {students_data['total']} students")
print()
for s in students_data["students"]:
    has_photo = "==> has_photo" if s.get("has_photo") else "   no_photo"
    samples = s.get("sample_count", 0)
    print(f"  {has_photo}  [{s['student_id']}] {s['name']}  class={s.get('class_name','')}  samples={samples}")

print()
print("  Photo endpoint: GET /api/students/{student_id}/photo")
print("  ML stats:       GET /api/students/ml-stats")
