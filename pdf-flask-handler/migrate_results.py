"""
将旧版结果（按 PDF 文件名命名）迁移为 Title 命名
在 AutoDL 上运行: python migrate_results.py
"""
import os
import re
import csv
import json
import shutil
from pathlib import Path

RESULTS_DIR = "/root/autodl-tmp/mineru_results"
CSV_PATH = "/root/autodl-tmp/ceramic_papers/Combined_Final_Metadata_Recovered.csv"


def sanitize_title(title, max_len=120):
    title = title.strip()
    title = re.sub(r'[<>:"/\\|?*]', "-", title)
    title = re.sub(r"\s+", " ", title)
    if len(title) > max_len:
        title = title[:max_len].rsplit(" ", 1)[0]
    return title


# 1. 建 CSV 映射: FullName → metadata
print("读取 CSV...")
csv_map = {}
with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        fullname = (row.get("FullName") or "").replace("\\", "/")
        title = (row.get("Title") or "").strip()
        if fullname and title:
            csv_map[fullname] = {
                "title": title,
                "authors": (row.get("Authors") or "").strip(),
                "journal": (row.get("Journal") or "").strip(),
                "year": (row.get("Publish_Year") or "").strip(),
                "doi": (row.get("DOI") or row.get("Recovered_DOI") or "").strip(),
                "abstract": (row.get("Abstract") or "").strip(),
                "keywords": (row.get("Keywords") or "").strip(),
            }

# 2. 找所有旧结果（.md 文件 = 已处理标记）
print("扫描已处理结果...")
md_files = []
for root, dirs, files in os.walk(RESULTS_DIR):
    dirs[:] = [d for d in dirs if not d.startswith(".")]
    for f in files:
        if f.endswith(".md") and f != "batch_log.md":
            md_files.append(os.path.join(root, f))

print(f"找到 {len(md_files)} 个已处理文件")

# 3. 逐个迁移
migrated = 0
skipped = 0
for md_path in md_files:
    # 旧文件路径: .../mineru_results/AIP/.../xxx.md
    rel = os.path.relpath(md_path, RESULTS_DIR).replace("\\", "/")
    # 转回 PDF 路径匹配 CSV: AIP/.../xxx.pdf
    pdf_rel = rel.replace(".md", ".pdf")

    meta = csv_map.get(pdf_rel)
    if meta is None:
        # 试试去掉 AIP 前缀
        pdf_rel2 = "AIP/" + pdf_rel if not pdf_rel.startswith("AIP/") else pdf_rel
        meta = csv_map.get(pdf_rel2)

    if meta is None:
        print(f"  ⚠ 无CSV匹配: {rel}")
        skipped += 1
        continue

    safe_title = sanitize_title(meta["title"])
    base_dir = os.path.dirname(md_path) if "/" in rel else RESULTS_DIR

    new_md = os.path.join(RESULTS_DIR, f"{safe_title}.md")
    new_json = os.path.join(RESULTS_DIR, f"{safe_title}.json")
    new_meta = os.path.join(RESULTS_DIR, f"{safe_title}_meta.json")

    # 防重名
    counter = 1
    while os.path.exists(new_md) and new_md != md_path:
        counter += 1
        safe_title_n = f"{safe_title}_{counter}"
        new_md = os.path.join(RESULTS_DIR, f"{safe_title_n}.md")
        new_json = os.path.join(RESULTS_DIR, f"{safe_title_n}.json")
        new_meta = os.path.join(RESULTS_DIR, f"{safe_title_n}_meta.json")

    print(f"  {Path(md_path).stem} -> {os.path.basename(new_md)}")

    # 重命名 md
    if md_path != new_md:
        shutil.move(md_path, new_md)
        print(f"    md 已移动")

    # 重命名 json
    old_json = md_path.replace(".md", ".json")
    if os.path.exists(old_json) and old_json != new_json:
        shutil.move(old_json, new_json)

    # 迁移 images
    old_images = md_path.replace(".md", "_images")
    if os.path.isdir(old_images):
        new_images = new_md.replace(".md", "_images")
        if old_images != new_images:
            if os.path.exists(new_images):
                shutil.rmtree(new_images, ignore_errors=True)
            shutil.move(old_images, new_images)

    # 保存 metadata
    if not os.path.exists(new_meta):
        with open(new_meta, "w", encoding="utf-8") as fh:
            json.dump(meta, fh, ensure_ascii=False, indent=2)

    migrated += 1

print(f"\n迁移完成: {migrated} 个 | 跳过(无CSV): {skipped}")

# 4. 清理空目录
for root, dirs, files in os.walk(RESULTS_DIR, topdown=False):
    if root == RESULTS_DIR:
        continue
    if not os.listdir(root):
        os.rmdir(root)
        print(f"  清理空目录: {root}")
