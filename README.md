# TRPG游戏服务器 - Docker部署指南

本项目是一个TRPG（桌面角色扮演游戏）游戏服务器，支持通过钉钉进行交互，并使用OpenAI的语言模型生成游戏内容。

## Docker部署

### 前提条件

- 安装 [Docker](https://docs.docker.com/get-docker/)
- 安装 [Docker Compose](https://docs.docker.com/compose/install/)（可选，但推荐）
- 获取OpenAI API密钥
- 获取钉钉机器人的Client ID和Client Secret

### 快速开始

1. **克隆仓库**

```bash
git clone <仓库地址>
cd <仓库目录>
```

2. **配置环境变量**

编辑`docker-compose.yml`文件，填入您的API密钥和钉钉凭证：

```yaml
environment:
  - OPENAI_API_KEY=your_api_key_here
  - OPENAI_MODEL=gpt-3.5-turbo
  - OPENAI_TEMP=0.7
  - DINGTALK_CLIENT_ID=your_client_id_here
  - DINGTALK_CLIENT_SECRET=your_client_secret_here
```

3. **构建并启动容器**

使用Docker Compose:

```bash
docker-compose up -d
```

或者使用Docker命令:

```bash
# 构建镜像
docker build -t trpg-server .

# 运行容器
docker run -d --name trpg-server \
  -v $(pwd)/config:/app/config \
  -e OPENAI_API_KEY=your_api_key_here \
  -e OPENAI_MODEL=gpt-3.5-turbo \
  -e OPENAI_TEMP=0.7 \
  -e DINGTALK_CLIENT_ID=your_client_id_here \
  -e DINGTALK_CLIENT_SECRET=your_client_secret_here \
  trpg-server
```

4. **查看日志**

```bash
docker logs -f trpg-server
```

### 配置文件

配置文件位于`config/`目录下，通过卷挂载到容器中。您可以修改这些配置文件而无需重新构建镜像：

- `config/ding_config.yaml`: 钉钉配置
- `config/game_config.yaml`: 游戏配置
- `config/llm_settings.yaml`: 语言模型设置

### 环境变量

服务器支持以下环境变量：

| 环境变量 | 描述 | 默认值 |
|---------|------|-------|
| `OPENAI_API_KEY` | OpenAI API密钥 | 无 |
| `OPENAI_MODEL` | 使用的模型名称 | gpt-3.5-turbo |
| `OPENAI_TEMP` | 模型温度参数 | 0.7 |
| `DINGTALK_CLIENT_ID` | 钉钉机器人Client ID | 无 |
| `DINGTALK_CLIENT_SECRET` | 钉钉机器人Client Secret | 无 |

## 开发指南

### 本地开发

1. 创建并激活虚拟环境

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
```

2. 安装依赖

```bash
pip install -r requirements.txt
```

3. 运行服务器

```bash
python main.py --config config/ding_config.yaml
```

### Docker开发

您可以使用Docker进行开发和测试：

```bash
# 构建开发镜像
docker build -t trpg-server:dev .

# 运行开发容器
docker run -it --rm \
  -v $(pwd):/app \
  -v $(pwd)/config:/app/config \
  -e OPENAI_API_KEY=your_api_key_here \
  trpg-server:dev bash
```

## 故障排除

### 常见问题

1. **容器无法启动**
   - 检查日志: `docker logs trpg-server`
   - 确保所有必需的环境变量都已设置

2. **API连接问题**
   - 确保API密钥正确
   - 检查网络连接

3. **配置文件问题**
   - 确保配置文件格式正确
   - 检查卷挂载是否正确

## 许可证

[添加您的许可证信息]
