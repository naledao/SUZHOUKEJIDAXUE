FROM docker.1ms.run/python:3.12-slim

# 设置工作目录
WORKDIR /app

# 复制依赖清单并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制脚本
COPY main.py .

COPY config.json .

# 容器启动时执行
CMD ["python", "main.py"]
