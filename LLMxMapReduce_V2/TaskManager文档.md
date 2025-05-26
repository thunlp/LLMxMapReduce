# 任务管理器 (Task Manager) 使用指南

## 概述

`task_manager` 是 LLMxMapReduce 系统的核心组件之一，负责管理所有任务的生命周期和状态。它使用 Redis 作为持久化存储，支持分布式部署和高并发访问。

## 架构设计

### 核心组件

```
┌─────────────────────────────────────────────────────────────┐
│                    Task Manager 架构                        │
├─────────────────────────────────────────────────────────────┤
│  Application Layer                                          │
│  ┌─────────────────┐    ┌─────────────────┐                │
│  │   API Service   │    │ Pipeline Manager │                │
│  └─────────────────┘    └─────────────────┘                │
│           │                       │                        │
│           └───────────┬───────────┘                        │
│                       │                                    │
│  ┌─────────────────────────────────────────────────────────┤
│  │            RedisTaskManager                             │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │  │ Task CRUD   │  │ Status Mgmt │  │ Health Check│     │
│  │  └─────────────┘  └─────────────┘  └─────────────┘     │
│  └─────────────────────────────────────────────────────────┤
│  Redis Storage Layer                                       │
│  ┌─────────────────────────────────────────────────────────┤
│  │  Key-Value Store: llm_task:{task_id}                   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │  │   Task 1    │  │   Task 2    │  │   Task N    │     │
│  │  │   Hash      │  │   Hash      │  │   Hash      │     │
│  │  └─────────────┘  └─────────────┘  └─────────────┘     │
│  └─────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────┘
```

## 任务状态管理

### 状态枚举

系统定义了以下任务状态：

```python
class TaskStatus(Enum):
    PENDING = "pending"              # 待处理
    PREPARING = "preparing"          # 准备中
    SEARCHING = "searching"          # 生成查询中
    SEARCHING_WEB = "searching_web"  # 搜索网页中
    CRAWLING = "crawling"           # 爬取内容中
    PROCESSING = "processing"       # 处理中
    COMPLETED = "completed"         # 已完成
    FAILED = "failed"              # 失败
    TIMEOUT = "timeout"            # 超时
```

### 状态流转图

```
┌─────────┐    ┌─────────────┐    ┌─────────────┐
│ PENDING │───▶│ PREPARING   │───▶│ SEARCHING   │
└─────────┘    └─────────────┘    └─────────────┘
                      │                   │
                      ▼                   ▼
               ┌─────────────┐    ┌─────────────┐
               │   FAILED    │    │SEARCHING_WEB│
               └─────────────┘    └─────────────┘
                      ▲                   │
                      │                   ▼
                      │            ┌─────────────┐
                      │            │  CRAWLING   │
                      │            └─────────────┘
                      │                   │
                      │                   ▼
                      │            ┌─────────────┐
                      └────────────│ PROCESSING  │
                                   └─────────────┘
                                          │
                                          ▼
                                   ┌─────────────┐
                                   │ COMPLETED   │
                                   └─────────────┘
                                          │
                                          ▼
                                   ┌─────────────┐
                                   │  TIMEOUT    │
                                   └─────────────┘
```

## Redis 数据结构

### 键命名规范

- **键前缀**: `llm_task:` (可配置)
- **完整键名**: `llm_task:{task_id}`
- **数据类型**: Redis Hash

### 任务数据结构

每个任务在 Redis 中存储为一个 Hash，包含以下字段：

```json
{
    "id": "uuid-string",
    "status": "pending|preparing|searching|...",
    "created_at": "2024-01-15T10:30:00.123456",
    "updated_at": "2024-01-15T10:35:00.654321",
    "start_time": "2024-01-15T10:30:05.000000",
    "end_time": "2024-01-15T10:45:30.000000",
    "params": "{\"topic\": \"AI研究\", \"top_n\": 100}",
    "error": "错误信息（如果有）",
    "original_topic": "AI研究",
    "expected_survey_title": "AI研究_uuid_timestamp"
}
```

### 字段说明

| 字段名 | 类型 | 说明 | 必需 |
|--------|------|------|------|
| `id` | String | 任务唯一标识符 | ✅ |
| `status` | String | 当前任务状态 | ✅ |
| `created_at` | ISO String | 任务创建时间 | ✅ |
| `updated_at` | ISO String | 最后更新时间 | ✅ |
| `start_time` | ISO String | 任务开始执行时间 | ❌ |
| `end_time` | ISO String | 任务完成时间 | ❌ |
| `params` | JSON String | 任务参数 | ✅ |
| `error` | String | 错误信息 | ❌ |
| `original_topic` | String | 原始主题 | ❌ |
| `expected_survey_title` | String | 预期综述标题 | ❌ |

## 核心功能

### 1. 任务创建

```python
# 创建新任务
task_id = str(uuid.uuid4())
params = {
    'topic': 'AI研究',
    'description': '人工智能最新进展',
    'top_n': 100
}

success = task_manager.create_task(task_id, params)
```

**Redis 操作**:
```redis
HSET llm_task:uuid-123 id "uuid-123"
HSET llm_task:uuid-123 status "pending"
HSET llm_task:uuid-123 created_at "2024-01-15T10:30:00.123456"
HSET llm_task:uuid-123 params "{\"topic\": \"AI研究\", ...}"
EXPIRE llm_task:uuid-123 86400
```

### 2. 状态更新

```python
# 更新任务状态
task_manager.update_task_status(
    task_id, 
    TaskStatus.PROCESSING,
    error=None
)
```

**Redis 操作**:
```redis
HSET llm_task:uuid-123 status "processing"
HSET llm_task:uuid-123 updated_at "2024-01-15T10:35:00.654321"
HSET llm_task:uuid-123 start_time "2024-01-15T10:35:00.654321"
```

### 3. 任务查询

```python
# 获取单个任务
task = task_manager.get_task(task_id)

# 获取任务列表
tasks = task_manager.list_tasks(
    status=TaskStatus.PROCESSING,
    limit=50
)
```

**Redis 操作**:
```redis
# 单个任务查询
HGETALL llm_task:uuid-123

# 任务列表查询
KEYS llm_task:*
# 然后对每个键执行 HGETALL
```

### 4. 字段更新

```python
# 更新特定字段
task_manager.update_task_field(
    task_id, 
    'original_topic', 
    '深度学习研究'
)
```

### 5. 任务删除

```python
# 删除任务
success = task_manager.delete_task(task_id)
```

**Redis 操作**:
```redis
DEL llm_task:uuid-123
```

## 高级功能

### 1. 健康检查

```python
# 检查 Redis 连接状态
is_healthy = task_manager.health_check()
```

### 2. 活跃任务统计

```python
# 获取活跃任务数量
active_count = task_manager.get_active_task_count()
```

### 3. 过期任务清理

```python
# 清理过期任务
expired_count = task_manager.cleanup_expired_tasks()
```

## 配置参数

### Redis 连接配置

```python
redis_config = {
    'host': 'localhost',        # Redis 主机地址
    'port': 6379,              # Redis 端口
    'db': 0,                   # 数据库索引
    'password': None,          # 密码（可选）
    'key_prefix': 'llm_task:', # 键前缀
    'expire_time': 86400       # 过期时间（秒）
}
```

### 连接池配置

```python
connection_pool_kwargs = {
    'max_connections': 50,           # 最大连接数
    'socket_keepalive': True,        # 启用 TCP keepalive
    'socket_keepalive_options': {}   # keepalive 选项
}
```

## 使用示例

### 完整的任务生命周期

```python
import uuid
from src.task_manager import get_task_manager, TaskStatus

# 1. 获取任务管理器实例
task_manager = get_task_manager({
    'host': 'localhost',
    'port': 6379,
    'db': 0
})

# 2. 创建任务
task_id = str(uuid.uuid4())
params = {
    'topic': 'AI研究',
    'description': '人工智能最新进展',
    'top_n': 100
}

# 创建任务
task_manager.create_task(task_id, params)

# 3. 更新状态流程
task_manager.update_task_status(task_id, TaskStatus.PREPARING)
task_manager.update_task_status(task_id, TaskStatus.SEARCHING)
task_manager.update_task_status(task_id, TaskStatus.SEARCHING_WEB)
task_manager.update_task_status(task_id, TaskStatus.CRAWLING)
task_manager.update_task_status(task_id, TaskStatus.PROCESSING)

# 4. 任务完成
task_manager.update_task_status(task_id, TaskStatus.COMPLETED)

# 5. 查询任务信息
task_info = task_manager.get_task(task_id)
print(f"任务执行时间: {task_info.get('execution_seconds', 0)} 秒")
```

### API 集成示例

```python
from flask import Blueprint, request, jsonify
from src.task_manager import get_task_manager, TaskStatus

api_bp = Blueprint('api', __name__)

@api_bp.route('/task/<task_id>', methods=['GET'])
def get_task_status(task_id: str):
    """获取任务状态"""
    task_manager = get_task_manager()
    task = task_manager.get_task(task_id)
    
    if not task:
        return jsonify({
            'success': False,
            'error': '任务不存在'
        }), 404
    
    return jsonify({
        'success': True,
        'task': task
    })

@api_bp.route('/tasks', methods=['GET'])
def list_tasks():
    """获取任务列表"""
    status = request.args.get('status')
    limit = int(request.args.get('limit', 100))
    
    task_manager = get_task_manager()
    
    # 状态过滤
    status_enum = None
    if status:
        try:
            status_enum = TaskStatus(status)
        except ValueError:
            return jsonify({
                'success': False,
                'error': f'无效的状态值: {status}'
            }), 400
    
    tasks = task_manager.list_tasks(status=status_enum, limit=limit)
    
    return jsonify({
        'success': True,
        'tasks': tasks,
        'count': len(tasks)
    })
```

## 性能优化

### 1. 连接池管理

- 使用连接池避免频繁建立连接
- 设置合适的最大连接数
- 启用 TCP keepalive 保持长连接

### 2. 批量操作

```python
# 使用 Pipeline 进行批量操作
with task_manager.redis_client.pipeline() as pipe:
    pipe.hset(key, mapping=task_data)
    pipe.expire(key, expire_time)
    pipe.execute()
```

### 3. 键过期策略

- 设置合理的过期时间（默认24小时）
- 定期清理过期任务
- 避免 Redis 内存溢出

## 监控和运维

### 1. 健康检查

```python
# 定期检查 Redis 连接
if not task_manager.health_check():
    logger.error("Redis 连接异常")
    # 触发告警或重连逻辑
```

### 2. 性能监控

```python
# 监控活跃任务数量
active_count = task_manager.get_active_task_count()
if active_count > 1000:
    logger.warning(f"活跃任务数量过多: {active_count}")

# 监控任务完成率
all_tasks = task_manager.list_tasks(limit=1000)
completed_tasks = [t for t in all_tasks if t['status'] == 'completed']
completion_rate = len(completed_tasks) / len(all_tasks) if all_tasks else 0
logger.info(f"任务完成率: {completion_rate:.2%}")
```

### 3. 错误处理

```python
try:
    task_manager.create_task(task_id, params)
except RedisError as e:
    logger.error(f"Redis 操作失败: {str(e)}")
    # 降级处理或重试逻辑
except Exception as e:
    logger.error(f"未知错误: {str(e)}")
    # 通用错误处理
```

## 故障排查

### 常见问题

1. **Redis 连接失败**
   - 检查 Redis 服务是否运行
   - 验证连接参数（host, port, password）
   - 检查网络连通性

2. **任务状态不更新**
   - 检查任务 ID 是否正确
   - 验证 Redis 键是否存在
   - 检查权限设置

3. **内存使用过高**
   - 检查过期时间设置
   - 清理无用的任务数据
   - 监控 Redis 内存使用

### 调试命令

```bash
# 连接 Redis 客户端
redis-cli

# 查看所有任务键
KEYS llm_task:*

# 查看特定任务
HGETALL llm_task:your-task-id

# 检查键的过期时间
TTL llm_task:your-task-id

# 查看 Redis 内存使用
INFO memory
```

## 最佳实践

1. **任务 ID 管理**
   - 使用 UUID 确保唯一性
   - 避免使用可预测的 ID

2. **状态更新**
   - 及时更新任务状态
   - 记录状态变更时间
   - 处理异常状态

3. **资源清理**
   - 定期清理过期任务
   - 监控 Redis 内存使用
   - 设置合理的过期时间

4. **错误处理**
   - 捕获并记录所有异常
   - 实现重试机制
   - 提供降级方案

5. **监控告警**
   - 监控任务执行状态
   - 设置性能阈值告警
   - 记录关键操作日志 