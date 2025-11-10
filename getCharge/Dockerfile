FROM python:3.12-slim

# 让 BuildKit 的代理 Build-Arg 有“落点”（即使传空也不报错）
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG http_proxy
ARG https_proxy
ARG ALL_PROXY
ARG all_proxy

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 运行期清空所有代理变量
ENV HTTP_PROXY="" HTTPS_PROXY="" http_proxy="" https_proxy="" ALL_PROXY="" all_proxy="" NO_PROXY="" no_proxy=""

# 删除 apt/pip 的持久化代理配置文件（若有）
RUN rm -f /etc/apt/apt.conf /etc/apt/apt.conf.d/*proxy || true \
 && rm -f /etc/pip.conf /root/.config/pip/pip.conf || true

# 关键：在当前 RUN 中临时取消所有代理，再更新并装构建依赖
RUN env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u all_proxy \
    apt-get update \
 && env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u all_proxy \
    apt-get install -y --no-install-recommends build-essential python3-dev curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先安装依赖（利用缓存层）
COPY requirements.txt ./
RUN env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u all_proxy \
    PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    python -m pip install --index-url https://pypi.org/simple -r requirements.txt

# 再复制源码
COPY . .

CMD ["python", "server.py"]
