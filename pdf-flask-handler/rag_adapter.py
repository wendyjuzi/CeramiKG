import os
import sys
import logging
import re
from elasticsearch import Elasticsearch

# 确保能找到 ragflow 源码
# 在 Docker 中我们将 ragflow 放在 /app/ragflow
RAGFLOW_PATH = os.environ.get("RAGFLOW_PATH", "/app/ragflow")
if RAGFLOW_PATH not in sys.path:
    sys.path.append(RAGFLOW_PATH)

# 配置一些 RAGFlow 需要的环境变量，防止导入时报错或行为异常
os.environ['HF_ENDPOINT'] = os.environ.get('HF_ENDPOINT', 'https://hf-mirror.com')

try:
    from deepdoc.parser.pdf_parser import RAGFlowPdfParser
except Exception as e:
    import traceback
    logging.warning(f"无法导入 RAGFlowPdfParser，详细错误: {e}")
    traceback.print_exc()
    RAGFlowPdfParser = None

try:
    from rag.nlp import rag_tokenizer
except ImportError:
    pass


class RAGAdapter:
    def __init__(self, es_client: Elasticsearch, index_name="rag_docs_deepdoc"):
        self.es = es_client
        self.index_name = index_name
        self.parser = RAGFlowPdfParser() if RAGFlowPdfParser else None

        # 确保索引存在
        if not self.es.indices.exists(index=self.index_name):
            self.create_index()

    def create_index(self):
        """创建一个简单的 ES 索引用于存储文档片段"""
        mapping = {
            "mappings": {
                "properties": {
                    "content": {"type": "text", "analyzer": "ik_max_word", "search_analyzer": "ik_smart"},
                    "doc_name": {"type": "keyword"},
                    "page_num": {"type": "integer"}
                }
            }
        }
        # 注意: ik_max_word 需要 ES 安装 IK 分词器，如果没有则用 standard
        try:
            self.es.indices.create(index=self.index_name, body=mapping)
        except Exception:
            # 如果失败(比如没有 IK)，尝试用默认分词
            basic_mapping = {
                "mappings": {
                    "properties": {
                        "content": {"type": "text"},
                        "doc_name": {"type": "keyword"},
                        "page_num": {"type": "integer"}
                    }
                }
            }
            try:
                self.es.indices.create(index=self.index_name, body=basic_mapping)
            except Exception as e:
                logging.info(f"索引创建跳过或失败: {e}")

    def parse_and_index(self, file_path, doc_name=None):
        """
        使用 DeepDoc 解析 PDF 并存入 ES
        """
        if not self.parser:
            logging.warning("RAGFlowPdfParser 未初始化，跳过 DeepDoc 解析: %s", file_path)
            return 0

        if not doc_name:
            doc_name = os.path.basename(file_path)

        logging.info(f"开始使用 RAGFlow DeepDoc 解析文件: {file_path}")

        # 读取文件二进制
        with open(file_path, 'rb') as f:
            file_content = f.read()

        # 调用 DeepDoc 解析
        try:
            # parser(fnm, need_image=True, ...) returns (chunks, tables)
            # fnm accepts bytes
            res = self.parser(file_content)
            if isinstance(res, tuple):
                chunks = res[0]
            else:
                chunks = res
        except Exception as e:
            logging.error(f"DeepDoc 解析失败: {e}")
            raise e

        logging.info(f"解析完成，共 {len(chunks)} 个块，开始存入 ES")
        return self._index_chunks(chunks, doc_name=doc_name)

    def parse_markdown_and_index(self, markdown_text, doc_name=None):
        """将 MinerU 产出的 Markdown 文本进行分块并存入 ES。"""
        if not markdown_text:
            raise ValueError("markdown_text 为空")

        if not doc_name:
            doc_name = "markdown_doc"

        chunks = self._split_markdown(markdown_text)
        logging.info(f"Markdown 分块完成，共 {len(chunks)} 个块，开始存入 ES")
        return self._index_chunks(chunks, doc_name=doc_name)

    def _split_markdown(self, markdown_text, max_chunk_chars=1000):
        """按段落与标题切分 Markdown，控制单块长度，避免超长块影响检索。"""
        text = markdown_text.replace("\r\n", "\n").strip()
        if not text:
            return []

        raw_blocks = [b.strip() for b in re.split(r"\n\s*\n+", text) if b.strip()]
        chunks = []

        for block in raw_blocks:
            # 对超长段落做二次切分，优先按句号切。
            if len(block) <= max_chunk_chars:
                chunks.append(block)
                continue

            sentences = re.split(r"(?<=[。！？.!?])\s+", block)
            current = ""
            for sent in sentences:
                sent = sent.strip()
                if not sent:
                    continue
                if len(current) + len(sent) + 1 <= max_chunk_chars:
                    current = f"{current} {sent}".strip()
                else:
                    if current:
                        chunks.append(current)
                    current = sent
            if current:
                chunks.append(current)

        return chunks

    def _index_chunks(self, chunks, doc_name):
        """统一写入 ES，兼容字符串与 DeepDoc 的 list 块结构。"""
        doc_count = 0
        for chunk in chunks:
            text_content = ""
            page_num = 0

            if isinstance(chunk, str):
                text_content = chunk
            elif isinstance(chunk, list):
                # deepdoc 有时返回 [text, bbox...]
                if len(chunk) > 0:
                    text_content = str(chunk[0])
            else:
                text_content = str(chunk)

            text_content = text_content.strip()
            if not text_content:
                continue

            doc = {
                "content": text_content,
                "doc_name": doc_name,
                "page_num": page_num
            }

            try:
                self.es.index(index=self.index_name, document=doc)
                doc_count += 1
            except Exception as e:
                logging.error(f"Indexing error: {e}")

        logging.info(f"索引完成: {doc_name}, 成功插入 {doc_count} 条")
        return doc_count

    def search(self, query_text, top_k=5):
        """
        简单的关键词检索
        """
        body = {
            "size": top_k,
            "query": {
                "match": {
                    "content": query_text
                }
            },
            "_source": ["content", "doc_name", "page_num"]
        }
        res = self.es.search(index=self.index_name, body=body)

        results = []
        for hit in res['hits']['hits']:
            results.append({
                "content": hit['_source']['content'],
                "score": hit['_score'],
                "doc_name": hit['_source']['doc_name']
            })
        return results
