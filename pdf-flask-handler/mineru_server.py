"""
MinerU GPU 解析服务 - 部署在 AutoDL 上
使用 magic-pdf CLI（MinerU 命令行）
启动: python mineru_server.py
端口: 8001
"""
import os
import re
import uuid
import shutil
import subprocess
import logging
from pathlib import Path
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- 配置 ---
UPLOAD_DIR = "/root/mineru_uploads"
OUTPUT_DIR = "/root/mineru_outputs"
SECRET_TOKEN = os.environ.get("MINERU_TOKEN", "ceramikg")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


def find_output_files(work_dir):
    """在 magic-pdf 输出目录中查找 md 和 json 文件"""
    result = {"md_content": "", "json_content": ""}

    for root, dirs, files in os.walk(work_dir):
        for f in files:
            if f.endswith(".md") and not result["md_content"]:
                with open(os.path.join(root, f), "r", encoding="utf-8") as fh:
                    result["md_content"] = fh.read()
            elif f.endswith("_content_list.json") or f.endswith("_content.json"):
                with open(os.path.join(root, f), "r", encoding="utf-8") as fh:
                    result["json_content"] = fh.read()
            elif f.endswith(".json"):
                # 可能还有其他 json
                pass
    return result


@app.route("/health", methods=["GET"])
def health():
    """健康检查"""
    # 检查 magic-pdf 是否可用
    try:
        r = subprocess.run(["magic-pdf", "--version"], capture_output=True, text=True, timeout=10)
        mineru_ready = r.returncode == 0
        version_info = r.stdout.strip() or r.stderr.strip()
    except Exception as e:
        mineru_ready = False
        version_info = str(e)

    # 检查 GPU
    try:
        import torch
        gpu_available = torch.cuda.is_available()
        gpu_name = torch.cuda.get_device_name(0) if gpu_available else "N/A"
    except:
        gpu_available = False
        gpu_name = "unknown"

    return jsonify({
        "status": "ok",
        "mineru_ready": mineru_ready,
        "mineru_version": version_info,
        "gpu_available": gpu_available,
        "gpu_name": gpu_name,
    })


@app.route("/parse", methods=["POST"])
def parse_pdf():
    """
    上传 PDF，返回 MinerU 解析结果
    Headers: X-Token: ceramikg
    Body: multipart/form-data, field name: file
    Returns: { "status": "success", "data": { "md_content": "...", "json_content": "..." } }
    """
    # 鉴权
    token = request.headers.get("X-Token", "")
    if token != SECRET_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files supported"}), 400

    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}.pdf")
    file.save(file_path)
    logger.info(f"收到文件: {file.filename} -> {file_id}")

    try:
        # --- 调用 magic-pdf CLI ---
        work_dir = os.path.join(OUTPUT_DIR, file_id)
        os.makedirs(work_dir, exist_ok=True)

        cmd = [
            "magic-pdf", "pdf-command",
            "--pdf", file_path,
            "--method", "auto",
            "--inside_model", "True",
            "--model_mode", "full",
        ]
        logger.info(f"执行: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 单文件最长 10 分钟
            cwd=work_dir,
        )

        logger.info(f"stdout: {result.stdout[-500:]}")
        if result.stderr:
            logger.info(f"stderr: {result.stderr[-500:]}")

        if result.returncode != 0:
            return jsonify({"error": f"magic-pdf failed: {result.stderr[-500:]}"}), 500

        # --- 查找输出文件 ---
        # magic-pdf 默认输出到 PDF 所在目录或当前目录的子目录
        output = find_output_files(work_dir)

        # 如果 work_dir 下没找到，试试 PDF 所在目录
        if not output["md_content"]:
            pdf_parent = os.path.dirname(file_path)
            for root, dirs, files in os.walk(pdf_parent):
                for f in files:
                    if f.endswith(".md"):
                        with open(os.path.join(root, f), "r", encoding="utf-8") as fh:
                            output["md_content"] = fh.read()
                        break
                if output["md_content"]:
                    break
            # 找 json
            for root, dirs, files in os.walk(pdf_parent):
                for f in files:
                    if "content_list" in f and f.endswith(".json"):
                        with open(os.path.join(root, f), "r", encoding="utf-8") as fh:
                            output["json_content"] = fh.read()
                        break
                if output["json_content"]:
                    break

        logger.info(f"解析完成: {file_id}, md: {len(output['md_content'])} 字符, json: {len(output['json_content'])} 字符")

        return jsonify({
            "status": "success",
            "data": output,
        })

    except subprocess.TimeoutExpired:
        logger.error(f"解析超时: {file_id}")
        return jsonify({"error": "Parse timeout (>10min)"}), 500
    except Exception as e:
        logger.error(f"解析失败: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

    finally:
        # 清理临时文件
        if os.path.exists(file_path):
            os.remove(file_path)
        # 清理输出
        out_dir = os.path.join(OUTPUT_DIR, file_id)
        if os.path.exists(out_dir):
            shutil.rmtree(out_dir, ignore_errors=True)
        # 清理 PDF 所在目录下的 magic-pdf 输出
        for item in os.listdir(UPLOAD_DIR):
            item_path = os.path.join(UPLOAD_DIR, item)
            if os.path.isdir(item_path) and item != os.path.basename(UPLOAD_DIR):
                try:
                    shutil.rmtree(item_path, ignore_errors=True)
                except:
                    pass


if __name__ == "__main__":
    logger.info("🚀 启动 MinerU GPU 解析服务 http://0.0.0.0:8001")
    app.run(host="0.0.0.0", port=8001)
