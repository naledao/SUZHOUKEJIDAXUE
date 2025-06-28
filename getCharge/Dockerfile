FROM docker.1ms.run/python:3.12-slim


# 设置工作目录
WORKDIR /app

# 复制依赖列表并安装
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 复制所有脚本和配置文件
COPY email.json .

COPY getCharge.py .

COPY headers.txt .

COPY roomInfo.json .

# 容器启动后执行脚本
CMD ["python", "getCharge.py"]