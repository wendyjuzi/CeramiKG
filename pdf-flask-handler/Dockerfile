FROM python:3.10-slim

# 优化国内网络连接 (Debian 镜像源 & PyPI 镜像源)
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources \
    && echo '[global]\nindex-url = https://mirrors.aliyun.com/pypi/simple/\ntrusted-host = mirrors.aliyun.com' > /etc/pip.conf

# 配置 HuggingFace 镜像 (用于后续下载模型)
ENV HF_ENDPOINT=https://hf-mirror.com
ENV UV_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libxcb1 \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        build-essential \
        gcc \
        python3-dev \
        pkg-config \
        libicu-dev \
    && rm -rf /var/lib/apt/lists/* \
    && pip install uv

COPY pdf-flask-handler/requirements.txt /app/requirements.txt
RUN uv pip install --system --no-cache -r /app/requirements.txt

# 复制并安装 RAGFlow (自动解析 pyproject.toml 依赖)
COPY ragflow-0.17.0 /app/ragflow
RUN uv pip install --system --no-cache -e /app/ragflow
ENV PYTHONPATH="${PYTHONPATH}:/app/ragflow"

# 安装 MinerU
COPY MinerU /app/MinerU
RUN uv pip install --system --no-cache -e /app/MinerU[pipeline]

# 下载模型数据 (NLTK, DeepDoc)
COPY pdf-flask-handler/download_models.py /app/download_models.py
RUN python3 /app/download_models.py

# 预构建 Trie 缓存 (减少启动时间)
RUN python3 -c "import sys; sys.path.append('/app/ragflow'); from rag.nlp import rag_tokenizer; rag_tokenizer.RagTokenizer()"

COPY pdf-flask-handler/app.py /app/app.py
COPY pdf-flask-handler/rag_adapter.py /app/rag_adapter.py
COPY pdf-flask-handler/uploads /app/uploads-sample
COPY pdf-flask-handler/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8001

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "-b", "0.0.0.0:8001", "--timeout", "600", "app:app"]