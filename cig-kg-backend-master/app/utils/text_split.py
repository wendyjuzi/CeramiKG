from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader, UnstructuredMarkdownLoader
import re
from typing import List


def text_split(file_path: str):
    # TODO:更改为实际文件
    loader = TextLoader(file_path, encoding="utf-8")
    documents = loader.load()

    # 配置递归字符文本分割器
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=3000,  # 每个块的最大字符数
        chunk_overlap=300,  # 块之间的重叠字符数
        separators=["\n\n", "。", "；", " ", "", "\n"]  # 中文友好的分隔符
    )

    chunks = text_splitter.split_documents(documents)

    return chunks


# TODO:按页分块
def split_text_by_pages():
    pass


# 按 token 分块
def split_text_by_chars(file_path: str, max_chars: int) -> List[str]:
    """
    将文本按字符数分割，确保每个片段的长度不超过最大字符数限制。

    :param file_path: 文件路径
    :param max_chars: 每个片段的最大字符数限制
    :return: 分割后的文本片段列表
    """

    # 打开并读取文件
    with open(file_path, "r", encoding="utf-8") as file:
        text = file.read()

    chunks = []
    current_chunk = ""
    current_chunk_length = 0

    # 按行分割文本
    lines = text.split("\n")

    for line in lines:
        line_length = len(line)

        # 如果当前行的长度超过最大字符数限制，则直接分割
        if line_length > max_chars:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""
                current_chunk_length = 0

            # 分割当前行
            while line_length > max_chars:
                chunks.append(line[:max_chars])
                line = line[max_chars:]
                line_length = len(line)

            current_chunk = line
            current_chunk_length = line_length
        else:
            # 如果当前片段加上新行的长度超过限制，则保存当前片段
            if current_chunk_length + line_length + 1 > max_chars:  # +1 是为了考虑换行符
                chunks.append(current_chunk)
                current_chunk = line
                current_chunk_length = line_length
            else:
                # 将当前行添加到当前片段
                if current_chunk:
                    current_chunk += "\n"
                current_chunk += line
                current_chunk_length += line_length + 1  # +1 是为了考虑换行符

    # 添加最后一个片段
    if current_chunk:
        chunks.append(current_chunk)

    return chunks


# 按标题分块
def split_md_file(file_path: str):
    """
    读取一个Markdown文件并按一个或多个#分块。
    :param file_path: Markdown文件的路径
    :return: 分块后的列表
    """
    try:
        # 打开并读取文件
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()

        # 按一级标题分块
        blocks = re.split("#####", content)

        # 去掉空字符串块（可选）
        blocks = [block.strip() for block in blocks if block.strip()]

        return blocks
    except FileNotFoundError:
        print(f"文件未找到：{file_path}")
        return []
    except Exception as e:
        print(f"读取文件时发生错误：{e}")
        return []


if __name__ == "__main__":
    chunks = text_split(file_path="../../doc_preprocessed/X6_1.md")
    for index, chunk in enumerate(chunks):
        print(f"{index}--------------------------------")
        print(chunk.page_content)


