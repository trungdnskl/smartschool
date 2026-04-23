"""Fix student names in InsightFace embeddings DB."""
import pickle, os

f = os.path.join("data", "face_embeddings", "deep_embeddings.pkl")
db = pickle.load(open(f, "rb"))

print("PKL structure:")
for k, v in db.items():
    if k == "students":
        print(f"  students: {type(v)}")
        if isinstance(v, dict):
            for sid, data in v.items():
                if isinstance(data, dict):
                    print(f"    {sid}: name={data.get('name')}, embs={len(data.get('embeddings', []))}")
    else:
        print(f"  {k}: {v}")

# Fix names based on LBPH data
name_map = {
    "HS001": "Nguyen Van An",
    "HS002": "Tran Thi Bich", 
    "HS003": "Dang Ngoc Trung",
}

students = db.get("students", {})
for sid, correct_name in name_map.items():
    if sid in students and isinstance(students[sid], dict):
        old_name = students[sid].get("name", "?")
        if old_name != correct_name:
            students[sid]["name"] = correct_name
            print(f"\nFIXED: {sid} '{old_name}' -> '{correct_name}'")

# Save
with open(f, "wb") as fp:
    pickle.dump(db, fp)
print("\nSaved!")
