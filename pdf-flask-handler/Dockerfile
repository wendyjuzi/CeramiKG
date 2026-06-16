FROM python:3.10-slim-bookworm

# 优化国内网络连接 (Debian 镜像源 & PyPI 镜像源)
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources \
    && echo '[global]\nindex-url = https://mirrors.aliyun.com/pypi/simple/\ntrusted-host = mirrors.aliyun.com' > /etc/pip.conf

# 配置 HuggingFace 镜像 (用于后续下载模型)
ENV HF_ENDPOINT=https://hf-mirror.com
ENV UV_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

ARG INSTALL_FULL_PDF_STACK=false

WORKDIR /app

RUN apt-get -o Acquire::Retries=5 update \
    && apt-get -o Acquire::Retries=5 install -y --no-install-recommends --fix-missing \
        libxcb1 \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install uv

COPY pdf-flask-handler/requirements.txt /app/requirements.txt
RUN uv pip install --system --no-cache -r /app/requirements.txt

# 复制并安装 RAGFlow (自动解析 pyproject.toml 依赖)
COPY ragflow-0.17.0 /app/ragflow
RUN if [ "$INSTALL_FULL_PDF_STACK" = "true" ]; then uv pip install --system --no-cache -e /app/ragflow; else echo "Skip RAGFlow dependency install"; fi
ENV PYTHONPATH="${PYTHONPATH}:/app/ragflow"

# 安装 MinerU
COPY MinerU /app/MinerU
RUN if [ "$INSTALL_FULL_PDF_STACK" = "true" ]; then uv pip install --system --no-cache -e /app/MinerU[pipeline]; else echo "Skip MinerU dependency install"; fi

# 下载模型数据 (NLTK, DeepDoc)
COPY pdf-flask-handler/download_models.py /app/download_models.py
RUN if [ "$INSTALL_FULL_PDF_STACK" = "true" ]; then python3 /app/download_models.py; else echo "Skip model downloads"; fi

# 预构建 Trie 缓存 (减少启动时间)
RUN if [ "$INSTALL_FULL_PDF_STACK" = "true" ]; then python3 -c "import sys; sys.path.append('/app/ragflow'); from rag.nlp import rag_tokenizer; rag_tokenizer.RagTokenizer()"; else echo "Skip RAG tokenizer warmup"; fi

COPY pdf-flask-handler/app.py /app/app.py
COPY pdf-flask-handler/rag_adapter.py /app/rag_adapter.py
COPY pdf-flask-handler/uploads /app/uploads-sample
COPY pdf-flask-handler/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8001

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "-b", "0.0.0.0:8001", "--timeout", "600", "app:app"]
