"""Build a submission .tar.gz bundle for Kaggle upload.

The bundle must have main.py and deck.csv at the top level (not nested),
along with the cg/ SDK directory.
"""
import os
import tarfile

ROOT = os.path.dirname(__file__)
SUBMISSION_DIR = os.path.join(ROOT, "sample_submission")
OUTPUT = os.path.join(ROOT, "submission.tar.gz")

REQUIRED = ["main.py", "deck.csv", "cg"]

def main():
    for name in REQUIRED:
        path = os.path.join(SUBMISSION_DIR, name)
        if not os.path.exists(path):
            print(f"ERROR: Missing required file: {path}")
            return

    def exclude_pycache(info):
        if "__pycache__" in info.name:
            return None
        return info

    with tarfile.open(OUTPUT, "w:gz") as tar:
        for item in os.listdir(SUBMISSION_DIR):
            full_path = os.path.join(SUBMISSION_DIR, item)
            tar.add(full_path, arcname=item, filter=exclude_pycache)
            print(f"  Added: {item}")

    size_mb = os.path.getsize(OUTPUT) / (1024 * 1024)
    print(f"\nCreated: {OUTPUT} ({size_mb:.1f} MB)")

if __name__ == "__main__":
    main()
