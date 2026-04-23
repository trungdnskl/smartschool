"""Test CRUD APIs for new relational schema."""
import requests

BASE = 'http://localhost:8001/api'

print('=== TEACHERS ===')
r = requests.post(f'{BASE}/teachers', data={'teacher_id': 'GV001', 'name': 'Nguyen Thi Mai', 'email': 'mai@school.vn', 'subject_specialty': 'Toan hoc'})
print('Create GV1:', r.json())
r = requests.post(f'{BASE}/teachers', data={'teacher_id': 'GV002', 'name': 'Tran Van Hung', 'email': 'hung@school.vn', 'subject_specialty': 'Vat ly'})
print('Create GV2:', r.json())
r = requests.get(f'{BASE}/teachers')
print('List:', r.json()['total'], 'teachers')

print('\n=== SUBJECTS ===')
r = requests.post(f'{BASE}/subjects', data={'subject_id': 'TOAN', 'name': 'Toan hoc', 'grade_level': '10-12'})
print('Create Toan:', r.json())
r = requests.post(f'{BASE}/subjects', data={'subject_id': 'VATLY', 'name': 'Vat ly', 'grade_level': '10-12'})
print('Create VatLy:', r.json())
r = requests.get(f'{BASE}/subjects')
print('List:', r.json()['total'], 'subjects')

print('\n=== CLASSES ===')
r = requests.post(f'{BASE}/classes', data={'class_id': '10A1', 'name': 'Lop 10A1', 'grade': '10', 'room': 'STEM-101', 'homeroom_teacher_id': 1})
print('Create 10A1:', r.json())
r = requests.post(f'{BASE}/classes', data={'class_id': '10A2', 'name': 'Lop 10A2', 'grade': '10', 'room': 'P.201', 'homeroom_teacher_id': 2})
print('Create 10A2:', r.json())
r = requests.get(f'{BASE}/classes')
data = r.json()
print('List:', data['total'], 'classes')
for c in data['classes']:
    teacher = c.get('teacher_name') or 'N/A'
    print(f"  {c['class_id']} - {c['name']} | GV: {teacher} | Phong: {c.get('room', '')}")

print('\n=== STUDENTS ===')
r = requests.post(f'{BASE}/students/enroll', data={'student_id': 'HS001', 'name': 'Le Van An', 'class_name': '10A1'})
print('Enroll HS001:', r.json())
r = requests.post(f'{BASE}/students/enroll', data={'student_id': 'HS002', 'name': 'Pham Thi Bich', 'class_name': '10A1'})
print('Enroll HS002:', r.json())
r = requests.get(f'{BASE}/students')
data = r.json()
print('List:', data['total'], 'students')
for s in data['students']:
    cls = s.get('class_display') or s.get('class_name', '')
    print(f"  {s['student_id']} - {s['name']} | Lop: {cls}")

print('\n=== STATS ===')
r = requests.get(f'{BASE}/stats')
stats = r.json()
print(f"GV: {stats.get('total_teachers', 0)} | Lop: {stats.get('total_classes', 0)} | HS: {stats['total_students']}")

print('\n=== ALL APIS OK ===')
