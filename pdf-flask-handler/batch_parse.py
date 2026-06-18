"""
批量 MinerU 解析脚本 - 在 AutoDL 上运行
功能：
  1. 读取 CSV，只处理 Title 非空的 PDF
  2. 解析结果文件以 Title 命名（而非 PDF 原名）
  3. 支持断点续传（跳过已处理的）
  4. 输出 md + json + images

用法: python batch_parse.py <PDF目录> <输出目录>
"""
import os
import re
import sys
import csv
import subprocess
import json
import shutil
import time
from pathlib import Path

PDF_DIR = sys.argv[1] if len(sys.argv) > 1 else "/root/autodl-tmp/ceramic_papers"
OUTPUT_DIR = sys.argv[2] if len(sys.argv) > 2 else "/root/autodl-tmp/mineru_results"
LOG_FILE = os.path.join(OUTPUT_DIR, "batch_log.jsonl")
MAGIC_TMP = "/tmp/magic-pdf"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─────────────────────────────────────────
# 1. 读取 CSV，建映射：PDF相对路径 → metadata
# ─────────────────────────────────────────
CSV_PATH = os.path.join(PDF_DIR, "Combined_Final_Metadata_Recovered.csv")
pdf_meta = {}  # key: 相对路径(Unix) → {title, authors, journal, year, doi, ...}

if os.path.exists(CSV_PATH):
    with open(CSV_PATH, "r", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            fullname = row.get("FullName", "").replace("\\", "/")
            title = (row.get("Title") or "").strip()
            if fullname and title:
                pdf_meta[fullname] = {
                    "title": title,
                    "authors": (row.get("Authors") or "").strip(),
                    "journal": (row.get("Journal") or "").strip(),
                    "year": (row.get("Publish_Year") or "").strip(),
                    "doi": (row.get("DOI") or row.get("Recovered_DOI") or "").strip(),
                    "abstract": (row.get("Abstract") or "").strip(),
                    "keywords": (row.get("Keywords") or "").strip(),
                }
    print(f"CSV 有效条目（有 Title）: {len(pdf_meta)}")


def sanitize_title(title, max_len=120):
    """去掉文件名非法字符"""
    title = title.strip()
    # 替换非法字符
    title = re.sub(r'[<>:"/\\|?*]', "-", title)
    # 合并多余空白
    title = re.sub(r"\s+", " ", title)
    # 截断
    if len(title) > max_len:
        title = title[:max_len].rsplit(" ", 1)[0]
    return title


# ─────────────────────────────────────────
# 2. 收集待处理的 PDF（只处理 CSV 中有 Title 的）
# ─────────────────────────────────────────
pdf_files = []
# 从日志恢复已处理的
processed = set()
if os.path.exists(LOG_FILE):
    with open(LOG_FILE, "r", encoding="utf-8") as fh:
        for line in fh:
            try:
                entry = json.loads(line.strip())
                if entry.get("status") == "success":
                    processed.add(entry.get("pdf", ""))
            except:
                pass

skipped_no_title = 0
skipped_done = 0

for root, dirs, files in os.walk(PDF_DIR):
    # 跳过 checkpoint 目录
    dirs[:] = [d for d in dirs if not d.startswith(".")]
    for f in files:
        if not f.lower().endswith(".pdf"):
            continue
        if f.startswith("."):
            continue

        pdf_path = os.path.join(root, f)
        rel_path = os.path.relpath(pdf_path, PDF_DIR).replace("\\", "/")

        # 已处理过？跳过
        if rel_path in processed:
            skipped_done += 1
            continue

        # 查 CSV 元数据
        meta = pdf_meta.get(rel_path)
        if meta is None:
            skipped_no_title += 1
            continue

        safe_title = sanitize_title(meta["title"])

        # 防重名
        final_title = safe_title
        counter = 1
        while os.path.isdir(os.path.join(OUTPUT_DIR, final_title)):
            counter += 1
            final_title = f"{safe_title}_{counter}"

        pdf_files.append((pdf_path, rel_path, meta, final_title))

total = len(pdf_files)
print(f"PDF 总数: {total + skipped_no_title + skipped_done}")
print(f"  跳过(无Title): {skipped_no_title}")
print(f"  跳过(已处理):  {skipped_done}")
print(f"  待处理:        {total}")
print(f"输出目录: {OUTPUT_DIR}")
print("=" * 60)

# ─────────────────────────────────────────
# 3. 批量处理
# ─────────────────────────────────────────
success = 0
failed = 0
start_all = time.time()

for i, (pdf_path, rel_path, meta, safe_title) in enumerate(pdf_files):
    print(f"[{i+1}/{total}] {safe_title[:70]} ... ", end="", flush=True)
    t0 = time.time()

    try:
        result = subprocess.run(
            [
                "magic-pdf", "pdf-command",
                "--pdf", pdf_path,
                "--method", "auto",
                "--inside_model", "True",
                "--model_mode", "full",
            ],
            capture_output=True,
            text=True,
            timeout=600,
        )

        elapsed = time.time() - t0

        if result.returncode != 0:
            err = result.stderr[-200:] if result.stderr else "unknown"
            print(f"FAILED ({elapsed:.0f}s): {err}")
            failed += 1
        else:
            pdf_stem = Path(pdf_path).stem
            parse_dir = os.path.join(MAGIC_TMP, pdf_stem, "auto")

            md_size = 0
            json_size = 0
            img_count = 0

            # --- 创建输出子目录 ---
            out_dir = os.path.join(OUTPUT_DIR, safe_title)
            os.makedirs(out_dir, exist_ok=True)

            # --- 复制 md ---
            md_path = os.path.join(parse_dir, f"{pdf_stem}.md")
            if os.path.exists(md_path):
                shutil.copy2(md_path, os.path.join(out_dir, f"{safe_title}.md"))
                md_size = os.path.getsize(md_path)
            else:
                for fn in os.listdir(parse_dir):
                    if fn.endswith(".md"):
                        shutil.copy2(os.path.join(parse_dir, fn),
                                     os.path.join(out_dir, f"{safe_title}.md"))
                        md_size = os.path.getsize(os.path.join(parse_dir, fn))
                        break

            # --- 复制 json ---
            json_path = os.path.join(parse_dir, f"{pdf_stem}_content_list.json")
            if os.path.exists(json_path):
                shutil.copy2(json_path, os.path.join(out_dir, "content_list.json"))
                json_size = os.path.getsize(json_path)

            # --- 复制图片 ---
            images_dir = os.path.join(parse_dir, "images")
            if os.path.isdir(images_dir):
                out_images_dir = os.path.join(out_dir, "images")
                shutil.copytree(images_dir, out_images_dir, dirs_exist_ok=True)
                img_count = len(os.listdir(out_images_dir))

            # --- 保存 metadata ---
            meta_path = os.path.join(out_dir, "meta.json")
            with open(meta_path, "w", encoding="utf-8") as fh:
                json.dump(meta, fh, ensure_ascii=False, indent=2)

            print(f"OK ({elapsed:.0f}s | md:{md_size} json:{json_size} img:{img_count})")
            success += 1

            # 日志
            with open(LOG_FILE, "a", encoding="utf-8") as log:
                log.write(json.dumps({
                    "idx": i + 1,
                    "total": total,
                    "pdf": rel_path,
                    "title": meta["title"],
                    "status": "success",
                    "elapsed_s": round(elapsed, 1),
                    "md_bytes": md_size,
                    "json_bytes": json_size,
                    "img_count": img_count,
                }, ensure_ascii=False) + "\n")

            # 清理 /tmp/magic-pdf/<stem>/
            tmp_dir = os.path.join(MAGIC_TMP, pdf_stem)
            if os.path.isdir(tmp_dir):
                shutil.rmtree(tmp_dir, ignore_errors=True)

    except subprocess.TimeoutExpired:
        print(f"TIMEOUT")
        failed += 1
    except Exception as e:
        print(f"ERROR: {e}")
        failed += 1

    # 每 50 个统计
    if (i + 1) % 50 == 0:
        elapsed_total = time.time() - start_all
        rate = (i + 1) / elapsed_total * 60
        eta = (total - i - 1) / rate if rate > 0 else 0
        print(f"--- 进度: {i+1}/{total} | 成功:{success} 失败:{failed} | {rate:.1f}篇/分 | 剩余:{eta:.0f}分 ---")

elapsed_total = time.time() - start_all
print("=" * 60)
print(f"全部完成！成功: {success}  失败: {failed}  总计: {total}")
print(f"总耗时: {elapsed_total/60:.1f} 分钟")
print(f"结果目录: {OUTPUT_DIR}")
