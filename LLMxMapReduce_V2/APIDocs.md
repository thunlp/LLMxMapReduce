# Pipeline服务API文档

## 概述

Pipeline服务提供RESTful API接口，支持任务管理、状态查询和数据库操作。所有API端点都以 `/api` 为前缀。

## 响应格式

所有API响应都采用统一的JSON格式：

```json
{
  "success": true/false,
  "data": {...},        // 成功时的数据
  "error": "错误信息"    // 失败时的错误描述
}
```

---

## 任务管理

### 提交任务

**POST** `/api/task/submit`

提交一个新的处理任务到Pipeline。

#### 请求体参数

| 参数名 | 类型 | 必需 | 描述 |
|--------|------|------|------|
| topic | string | 是* | 研究主题 |
| description | string | 否 | 主题描述 |
| output_file | string | 否 | 输出文件路径 |
| config_file | string | 否 | 配置文件路径 |
| search_model | string | 否 | 搜索模型 |
| block_count | integer | 否 | 块数量 |
| data_num | integer | 否 | 数据数量 |
| top_n | integer | 否 | 返回结果数量 |
| input_file | string | 否 | 输入文件路径（与topic互斥） |

*注：topic和input_file二选一

#### 响应示例

```json
{
  "success": true,
  "task_id": "task_12345",
  "message": "任务已提交",
  "output_file": "/path/to/output.json",
  "original_topic": "研究主题",
  "unique_survey_title": "生成的调研标题"
}
```

#### 错误响应

- `500` - Pipeline管理器未初始化或内部错误

---

### 获取任务状态

**GET** `/api/task/{task_id}`

获取指定任务的详细状态信息。

#### 路径参数

| 参数名 | 类型 | 描述 |
|--------|------|------|
| task_id | string | 任务ID |

#### 响应示例

```json
{
  "success": true,
  "task": {
    "id": "task_12345",
    "status": "running",
    "params": {...},
    "created_at": "2025-05-27T10:00:00Z",
    "updated_at": "2025-05-27T10:05:00Z"
  }
}
```

#### 错误响应

- `404` - 任务不存在

---

### 获取任务Pipeline状态

**GET** `/api/task/{task_id}/pipeline_status`

获取任务相关的Pipeline详细运行状态。

#### 路径参数

| 参数名 | 类型 | 描述 |
|--------|------|------|
| task_id | string | 任务ID |

#### 响应示例

```json
{
  "success": true,
  "task_id": "task_12345",
  "status": "running",
  "pipeline_running": true,
  "is_global_pipeline": true,
  "nodes": [
    {
      "name": "node_1",
      "is_running": true,
      "status": "运行中",
      "queue_size": 10,
      "max_queue_size": 100,
      "executing_count": 2,
      "worker_count": 4
    }
  ]
}
```

---

### 获取任务列表

**GET** `/api/tasks`

获取任务列表，支持状态过滤和数量限制。

#### 查询参数

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|--------|------|------|--------|------|
| status | string | 否 | - | 状态过滤 |
| limit | integer | 否 | 100 | 返回数量限制 |

#### 响应示例

```json
{
  "success": true,
  "tasks": [
    {
      "id": "task_12345",
      "status": "completed",
      "created_at": "2025-05-27T10:00:00Z"
    }
  ],
  "count": 1,
  "global_pipeline_mode": true
}
```

#### 错误响应

- `400` - 无效的状态值

---

### 删除任务

**DELETE** `/api/task/{task_id}`

删除指定的任务。

#### 路径参数

| 参数名 | 类型 | 描述 |
|--------|------|------|
| task_id | string | 任务ID |

#### 响应示例

```json
{
  "success": true,
  "message": "任务 task_12345 已删除"
}
```

#### 错误响应

- `400` - 删除任务失败

---

## 结果获取

### 获取任务输出

**GET** `/api/output/{task_id}`

获取已完成任务的输出结果。

#### 路径参数

| 参数名 | 类型 | 描述 |
|--------|------|------|
| task_id | string | 任务ID |

#### 响应示例

```json
{
  "success": true,
  "content": "任务输出内容",
  "source": "database",
  "metadata": {
    "created_at": "2025-05-27T10:00:00Z",
    "title": "调研标题",
    "status": "completed"
  }
}
```

#### 错误响应

- `404` - 任务不存在或输出结果不存在
- `400` - 任务尚未完成

---

## 系统状态

### 全局Pipeline状态

**GET** `/api/global_pipeline_status`

获取全局Pipeline的运行状态和统计信息。

#### 响应示例

```json
{
  "success": true,
  "pipeline_initialized": true,
  "pipeline_running": true,
  "active_tasks_count": 5,
  "total_tasks_count": 20,
  "nodes": [
    {
      "name": "processor_node",
      "is_running": true,
      "status": "运行中",
      "queue_size": 15,
      "max_queue_size": 100,
      "executing_count": 3,
      "worker_count": 5
    }
  ]
}
```

---

### 服务健康检查

**GET** `/api/health`

检查服务及其依赖组件的健康状态。

#### 响应示例

```json
{
  "success": true,
  "services": {
    "redis": {
      "status": "healthy",
      "required": true
    },
    "mongodb": {
      "status": "healthy",
      "required": false
    }
  }
}
```

#### 状态码

- `200` - 所有必需服务健康
- `503` - 必需服务不健康

---

## 数据库操作

### 数据库统计信息

**GET** `/api/database/stats`

获取数据库的统计信息。

#### 响应示例

```json
{
  "success": true,
  "stats": {
    "total_surveys": 100,
    "active_surveys": 25,
    "storage_size": "1.2GB"
  }
}
```

#### 错误响应

- `503` - 数据库不可用

---

### 数据库健康检查

**GET** `/api/database/health`

检查数据库连接状态。

#### 响应示例

```json
{
  "success": true,
  "status": "healthy",
  "message": "数据库连接正常"
}
```

#### 状态码

- `200` - 数据库健康
- `503` - 数据库不可用或连接失败

---

## 错误码说明

| 状态码 | 说明 |
|--------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |
| 503 | 服务不可用 |

## 任务状态说明

任务状态包括但不限于：
- `pending` - 等待中
- `running` - 运行中
- `completed` - 已完成
- `failed` - 失败
- `cancelled` - 已取消

## 注意事项

1. 所有时间戳使用ISO 8601格式
2. 文件路径使用绝对路径
3. 任务ID由系统自动生成
4. Pipeline采用全局模式运行
5. 输出结果优先从数据库获取，文件作为备选方案