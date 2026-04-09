import os
from pathlib import Path


def get_image_path(relative_path: str) -> str:
    """验证并返回图片的绝对路径"""
    # 假设图片存储在项目根目录的 `/images` 下
    base_dir = Path(__file__).parent.parent.parent  # 项目根目录
    image_path = base_dir / "images" / relative_path

    print(image_path)

    # 安全检查：防止路径遍历攻击
    if not str(image_path).startswith(str(base_dir)):
        raise ValueError("非法路径")

    if not image_path.exists():
        raise FileNotFoundError(f"图片路径不存在: {relative_path}")

    return str(image_path)