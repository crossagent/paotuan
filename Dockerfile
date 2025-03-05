# 使用Python 3.12.6镜像作为基础镜像
FROM python:3.12.6-slim

# 设置工作目录
WORKDIR /app

# 复制依赖文件并安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码到容器
COPY . .

# 创建配置目录（如果不存在）
RUN mkdir -p /app/config

# 设置启动命令
CMD ["python", "main.py", "--config", "/app/config/ding_config.yaml"]
