import os
import shutil
import nltk
from huggingface_hub import snapshot_download

# Define constants
BASE_DIR = "/app/ragflow"
RES_DIR = os.path.join(BASE_DIR, "rag/res")
DEEPDOC_DIR = os.path.join(RES_DIR, "deepdoc")

# Ensure directories exist
os.makedirs(DEEPDOC_DIR, exist_ok=True)

# 1. Download NLTK Data
print("Downloading NLTK data...")
# Set NLTK data path to system-wide location to avoid permission issues or confusion
nltk_data_path = "/usr/local/share/nltk_data"
nltk.data.path.append(nltk_data_path)
os.makedirs(nltk_data_path, exist_ok=True)

import socket
socket.setdefaulttimeout(30)

for res in ['wordnet', 'punkt', 'punkt_tab']:
    print(f"Downloading {res}...")
    try:
        nltk.download(res, download_dir=nltk_data_path)
    except Exception as e:
        print(f"Failed to download {res}: {e}")

# 2. Download DeepDoc Models
print("Downloading DeepDoc models from HuggingFace...")
# Set endpoint for China mirror if needed
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

def download_repo(repo_id, local_dir):
    print(f"Snapshot download: {repo_id} -> {local_dir}")
    try:
        snapshot_download(repo_id=repo_id, local_dir=local_dir, local_dir_use_symlinks=False)
    except Exception as e:
        print(f"Failed to download {repo_id}: {e}")
        # Non-critical for build process, but runtime might fail

# Download deepdoc (OCR, Layout, TSR models)
download_repo("InfiniFlow/deepdoc", DEEPDOC_DIR)

# Download text_concat_xgb (XGBoost model for text merging)
download_repo("InfiniFlow/text_concat_xgb_v1.0", DEEPDOC_DIR)

print("Download script completed.")
