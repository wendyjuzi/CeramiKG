import os
import sys
import logging
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
            raise ImportError("RAGFlowPdfParser 未初始化")

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

        # 批量写入 ES
        doc_count = 0
        for i, chunk in enumerate(chunks):
            # 防御性处理 chunk 格式
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
