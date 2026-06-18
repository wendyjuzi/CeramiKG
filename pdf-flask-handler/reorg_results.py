"""
整理 mineru_results：将平铺文件按 Title 归入文件夹
结构: {Title}/ {Title}.md, {Title}.json, images/, meta.json
在 AutoDL 上运行: python reorg_results.py
"""
import os, re, shutil, json

RESULTS_DIR = "/root/autodl-tmp/mineru_results"

# 找到所有 Title 命名的 .md 文件（在根目录下）
mds = [f for f in os.listdir(RESULTS_DIR) if f.endswith(".md") and f != "batch_log.md"]
print(f"找到 {len(mds)} 个 md 文件")

for md_file in mds:
    title = md_file[:-3]  # 去掉 .md
    folder = os.path.join(RESULTS_DIR, title)

    # 跳过已是文件夹的
    if os.path.isdir(folder):
        continue

    os.makedirs(folder, exist_ok=True)

    # 移动 md
    src_md = os.path.join(RESULTS_DIR, md_file)
    dst_md = os.path.join(folder, md_file)
    shutil.move(src_md, dst_md)

    # 移动 json
    json_file = title + ".json"
    src_json = os.path.join(RESULTS_DIR, json_file)
    if os.path.exists(src_json):
        shutil.move(src_json, os.path.join(folder, json_file))

    # 移动 meta
    meta_file = title + "_meta.json"
    src_meta = os.path.join(RESULTS_DIR, meta_file)
    if os.path.exists(src_meta):
        shutil.move(src_meta, os.path.join(folder, "meta.json"))

    # 移动 images
    images_dir = title + "_images"
    src_images = os.path.join(RESULTS_DIR, images_dir)
    if os.path.isdir(src_images):
        dst_images = os.path.join(folder, "images")
        if os.path.exists(dst_images):
            shutil.rmtree(dst_images)
        shutil.move(src_images, dst_images)

    print(f"  ✅ {title[:60]}")

print("整理完成！")
