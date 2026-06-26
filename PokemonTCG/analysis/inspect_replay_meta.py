import json, os

path = "C:/Users/adiku/.cache/kagglehub/datasets/kaggle/pokemon-tcg-ai-battle-episodes-2026-06-16/versions/1"
files = sorted(os.listdir(path))

for f in files[:3]:
    with open(os.path.join(path, f)) as fh:
        data = json.load(fh)
    teams = data["info"].get("TeamNames", [])
    rewards = data.get("rewards", [])
    info_keys = list(data["info"].keys())
    print(f"{f}: teams={teams}, rewards={rewards}")
    print(f"  info keys: {info_keys}")
    agents = data["info"].get("Agents", [])
    if agents:
        for a in agents:
            if isinstance(a, dict):
                print(f"  agent: {list(a.keys())}")
            else:
                print(f"  agent: {a}")
    print()
