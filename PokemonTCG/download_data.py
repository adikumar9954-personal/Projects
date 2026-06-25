import shutil
from pathlib import Path

import kagglehub

dest = Path(__file__).parent

path = Path(kagglehub.competition_download("pokemon-tcg-ai-battle"))
print(f"Downloaded to: {path}")

for item in path.iterdir():
    target = dest / item.name
    if target.exists():
        continue
    if item.is_dir():
        shutil.copytree(item, target)
    else:
        shutil.copy2(item, target)
    print(f"  Copied: {item.name}")

print("Done.")
