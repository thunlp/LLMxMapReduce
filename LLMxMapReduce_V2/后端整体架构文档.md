# LLMxMapReduce Web服务 - 重构版本

## 概述

这是LLMxMapReduce项目的重构版本，采用事件驱动架构，支持Redis任务管理、MongoDB数据存储和分布式部署。

## 架构特点

### 1. 事件驱动架构
- 基于Redis的任务状态管理
- 异步任务处理
- 支持分布式部署

### 2. 模块化设计
- **任务管理模块** (`src/task_manager.py`): Redis任务存储和状态管理
- **Pipeline处理器** (`src/pipeline_processor.py`): 任务处理和监控
- **API服务模块** (`src/api_service.py`): RESTful API接口
- **配置管理模块** (`src/config_manager.py`): 集中配置管理

### 3. 数据存储
- **Redis**: 任务状态和元数据存储
- **MongoDB**: 综述结果存储（可选）
- **文件系统**: 备选存储方案

## 安装和配置

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 启动Redis服务
```bash
# 使用Docker
docker run -d --name redis -p 6379:6379 redis:latest

# 或使用本地Redis
redis-server
```

### 3. 启动MongoDB（可选）
```bash
# 使用Docker
docker run -d --name mongodb -p 27017:27017 mongo:latest
```

### 4. 配置环境变量
```bash
export REDIS_HOST=localhost
export REDIS_PORT=6379
export MONGO_URI=mongodb://localhost:27017/
export OPENAI_API_KEY=your_api_key
export OPENAI_API_BASE=your_api_base
export SERPER_API_KEY=your_serper_key
```

## 使用方法

### 1. 启动服务
```bash
python app.py
```

### 2. 命令行参数
```bash
python app.py --help
```

可用参数：
- `--config`: 配置文件路径
- `--language`: 提示语言 (zh/en)
- `--host`: 服务器主机地址
- `--port`: 服务器端口
- `--redis-host`: Redis主机地址
- `--redis-port`: Redis端口

### 3. API接口

#### 启动任务
```bash
POST /api/start_pipeline
Content-Type: application/json

{
    "topic": "机器学习",
    "description": "深度学习在自然语言处理中的应用",
    "top_n": 100
}
```

#### 查询任务状态
```bash
GET /api/task/{task_id}
```

#### 获取任务结果
```bash
GET /api/output/{task_id}
```

#### 获取任务列表
```bash
GET /api/tasks?status=completed&limit=50
```

#### 健康检查
```bash
GET /api/health
```

## 任务状态

任务状态使用枚举类型管理：

- `PENDING`: 待处理
- `PREPARING`: 准备中
- `SEARCHING`: 生成查询中
- `SEARCHING_WEB`: 搜索网页中
- `CRAWLING`: 爬取内容中
- `PROCESSING`: 处理中
- `COMPLETED`: 已完成
- `FAILED`: 失败
- `TIMEOUT`: 超时

## 配置管理

### 1. 配置文件示例
```json
{
    "redis": {
        "host": "localhost",
        "port": 6379,
        "db": 0,
        "key_prefix": "llm_task:",
        "expire_time": 86400
    },
    "mongo": {
        "uri": "mongodb://localhost:27017/",
        "database": "llm_survey",
        "collection": "surveys"
    },
    "pipeline": {
        "config_file": "config/model_config_ds.json",
        "parallel_num": 3,
        "check_interval": 30,
        "timeout": 3600
    },
    "api": {
        "host": "0.0.0.0",
        "port": 5000,
        "debug": false,
        "cors_enabled": true
    },
    "logging": {
        "level": "INFO",
        "file_enabled": true,
        "file_path": "logs/web_demo.log"
    }
}
```

### 2. 环境变量优先级
环境变量会覆盖配置文件中的设置。

## 监控和日志

### 1. 日志配置
- 支持文件和控制台输出
- 自动日志轮转
- 可配置日志级别

### 2. 监控指标
- 活跃任务数量
- Pipeline状态
- Redis连接状态
- MongoDB连接状态

## 部署

### 1. Docker部署
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 5000

CMD ["python", "app.py"]
```

### 2. 生产环境建议
- 使用Gunicorn或uWSGI作为WSGI服务器
- 配置Nginx作为反向代理
- 使用Redis Cluster提高可用性
- 配置MongoDB副本集

## 故障排除

### 1. 常见问题
- **Redis连接失败**: 检查Redis服务状态和网络连接
- **任务超时**: 调整timeout配置或检查Pipeline性能
- **内存不足**: 调整parallel_num参数

### 2. 日志查看
```bash
tail -f logs/web_demo.log
```

## 开发指南

### 1. 代码结构
```
LLMxMapReduce_V2/
├── app.py                    # 主应用程序
├── src/
│   ├── task_manager.py       # 任务管理
│   ├── pipeline_processor.py # Pipeline处理
│   ├── api_service.py        # API服务
│   ├── config_manager.py     # 配置管理
│   └── ...
├── config/                   # 配置文件
├── logs/                     # 日志文件
└── requirements.txt          # 依赖列表
```

### 2. 扩展开发
- 继承`TaskProcessor`类实现新的任务处理器
- 在`api_service.py`中添加新的API接口
- 在`config_manager.py`中添加新的配置项

## 性能优化

### 1. Redis优化
- 使用连接池
- 配置合适的过期时间
- 使用Pipeline批量操作

### 2. Pipeline优化
- 调整worker数量
- 优化队列大小
- 使用异步处理

## 安全考虑

### 1. API安全
- 添加认证和授权
- 限制请求频率
- 输入验证

### 2. 数据安全
- Redis密码保护
- MongoDB访问控制
- 敏感信息加密

## 许可证

[添加许可证信息]

## 贡献

欢迎提交Issue和Pull Request。

## 联系方式

[添加联系方式] 