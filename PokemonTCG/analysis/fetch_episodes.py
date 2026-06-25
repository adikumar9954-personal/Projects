"""Fetch top battle episodes from the Kaggle dataset.

The index dataset contains a manifest.csv pointing to daily episode datasets.
Each daily dataset is large (~20GB), so this script lets you selectively download.

Usage:
    python analysis/fetch_episodes.py                  # Show manifest (available dates)
    python analysis/fetch_episodes.py 2026-06-23       # Download a specific day's episodes
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import kagglehub

INDEX_DATASET = "kaggle/pokemon-tcg-ai-battle-episodes-index"

def fetch_manifest() -> pd.DataFrame:
    path = kagglehub.dataset_download(INDEX_DATASET)
    df = pd.read_csv(os.path.join(path, "manifest.csv"))
    return df

def fetch_daily_episodes(date: str) -> str:
    slug = f"kaggle/pokemon-tcg-ai-battle-episodes-{date}"
    path = kagglehub.dataset_download(slug)
    print(f"Downloaded to: {path}")
    for f in os.listdir(path):
        size_mb = os.path.getsize(os.path.join(path, f)) / (1024 * 1024)
        print(f"  {f} ({size_mb:.1f} MB)")
    return path

if __name__ == "__main__":
    manifest = fetch_manifest()

    if len(sys.argv) > 1:
        date = sys.argv[1]
        if date not in manifest["date"].values:
            print(f"Date '{date}' not found. Available dates:")
            print(manifest[["date", "episode_count", "top_avg_score"]].to_string(index=False))
            sys.exit(1)
        fetch_daily_episodes(date)
    else:
        print("Available episode dates:\n")
        print(manifest[["date", "episode_count", "total_bytes", "top_avg_score", "median_avg_score"]].to_string(index=False))
        print(f"\nTo download a day: python analysis/fetch_episodes.py <date>")
