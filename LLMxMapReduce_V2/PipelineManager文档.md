# Pipeline处理器架构文档

## 概述

`pipeline_processor.py` 是 LLMxMapReduce 系统的核心组件之一，负责管理和协调整个综述生成流水线的任务处理。该模块实现了一个完整的任务生命周期管理系统，包括任务提交、处理、监控和清理。

## 系统架构

### 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    Pipeline处理器模块                        │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌─────────────────────────────────┐  │
│  │  TaskProcessor  │    │    PipelineTaskManager         │  │
│  │   (抽象基类)     │    │      (任务管理器)               │  │
│  └─────────────────┘    └─────────────────────────────────┘  │
│           │                           │                      │
│           ▼                           ▼                      │
│  ┌─────────────────┐    ┌─────────────────────────────────┐  │
│  │TopicSearchProc- │    │        任务生命周期管理          │  │
│  │essor (主题搜索) │    │  • 任务提交和初始化              │  │
│  └─────────────────┘    │  • 状态监控                     │  │
│                         │  • 结果处理                     │  │
│                         │  • 资源清理                     │  │
│                         └─────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## 核心组件

### 1. TaskProcessor (任务处理器抽象基类)

**功能**: 定义了任务处理器的标准接口

**设计模式**: 抽象工厂模式

```python
class TaskProcessor(ABC):
    @abstractmethod
    async def process(self, task_id: str, params: Dict[str, Any]) -> Optional[str]:
        """处理任务的核心方法"""
        pass
```

**特点**:
- 使用抽象基类确保所有处理器实现统一接口
- 支持异步处理，提高系统并发性能
- 返回处理结果路径，便于后续流程使用

### 2. TopicSearchProcessor (主题搜索处理器)

**功能**: 负责处理主题搜索和网页爬取任务

**工作流程**:
```
输入主题 → 生成查询 → 搜索网页 → 爬取内容 → 输出结果文件
```

**详细步骤**:

1. **查询生成阶段**
   - 使用 LLM 根据主题和描述生成多个搜索查询
   - 状态更新: `TaskStatus.SEARCHING`

2. **网页搜索阶段**
   - 批量执行网页搜索，获取相关URL列表
   - 状态更新: `TaskStatus.SEARCHING_WEB`

3. **内容爬取阶段**
   - 异步爬取网页内容
   - 状态更新: `TaskStatus.CRAWLING`
   - 输出格式: JSONL文件

**配置参数**:
- `search_model`: 搜索使用的LLM模型 (默认: gemini-2.0-flash-thinking-exp-01-21)
- `top_n`: 爬取的网页数量 (默认: 100)
- `each_query_result`: 每个查询返回的结果数 (默认: 10)

### 3. PipelineTaskManager (Pipeline任务管理器)

**功能**: 管理任务的完整生命周期

**核心职责**:
- 任务提交和初始化
- 任务状态监控
- 任务结果处理
- 资源清理

#### 3.1 任务提交流程

```python
def submit_task(self, params: Dict[str, Any]) -> str:
```

**流程图**:
```
接收任务参数 → 生成唯一任务ID → 创建唯一综述标题 → 
准备输出路径 → 创建任务记录 → 启动处理线程 → 返回任务ID
```

**关键特性**:
- **唯一性保证**: 使用UUID + 时间戳确保任务ID唯一
- **标题唯一化**: 生成格式为 `{原始主题}_{任务ID}_{时间戳}` 的唯一标题
- **异步处理**: 使用独立线程处理任务，避免阻塞主线程

#### 3.2 任务执行流程

```python
def _run_task(self, task_id: str):
```

**执行步骤**:

1. **准备阶段**
   - 获取任务参数
   - 状态更新: `TaskStatus.PREPARING`

2. **输入处理**
   - 如果是主题任务: 调用 `TopicSearchProcessor` 进行搜索和爬取
   - 如果是文件任务: 验证输入文件存在性

3. **文件预处理**
   - 修改输入文件，添加唯一标题和任务ID
   - 创建临时文件避免影响原始数据

4. **Pipeline提交**
   - 状态更新: `TaskStatus.PROCESSING`
   - 启动任务监控
   - 将处理后的文件提交到全局Pipeline

#### 3.3 任务监控机制

```python
def _monitor_task(self, task_id: str):
```

**监控策略**:
- **轮询检查**: 定期检查数据库中的任务完成状态
- **超时处理**: 设置任务超时时间，防止任务无限期运行
- **状态同步**: 实时更新任务状态到Redis

**监控流程**:
```
开始监控 → 定期检查数据库 → 检测到完成/超时 → 更新状态 → 清理资源
```

#### 3.4 资源管理

**临时文件管理**:
- 创建格式: `{原始文件}.{任务ID}.tmp`
- 自动清理: 任务完成或超时后自动删除临时文件

**内存管理**:
- 使用守护线程避免内存泄漏
- 及时释放不再使用的资源

## 数据流

### 1. 主题搜索任务数据流

```
用户输入主题
    ↓
TopicSearchProcessor.process()
    ↓
LLM生成查询 → 网页搜索 → 内容爬取
    ↓
生成JSONL文件
    ↓
文件预处理(添加唯一标题)
    ↓
提交到全局Pipeline
    ↓
监控任务完成状态
    ↓
清理临时资源
```

### 2. 文件输入任务数据流

```
用户提供输入文件
    ↓
验证文件存在性
    ↓
文件预处理(添加唯一标题)
    ↓
提交到全局Pipeline
    ↓
监控任务完成状态
    ↓
清理临时资源
```

## 状态管理

### 任务状态枚举

| 状态 | 描述 | 触发条件 |
|------|------|----------|
| `PREPARING` | 准备中 | 任务开始执行 |
| `SEARCHING` | 生成查询中 | 开始LLM查询生成 |
| `SEARCHING_WEB` | 网页搜索中 | 开始批量网页搜索 |
| `CRAWLING` | 爬取中 | 开始网页内容爬取 |
| `PROCESSING` | 处理中 | 提交到Pipeline处理 |
| `COMPLETED` | 已完成 | 检测到数据库中任务完成 |
| `FAILED` | 失败 | 任务执行过程中出现异常 |
| `TIMEOUT` | 超时 | 任务执行时间超过设定阈值 |

### 状态转换图

```
PREPARING → SEARCHING → SEARCHING_WEB → CRAWLING → PROCESSING
    ↓           ↓            ↓             ↓          ↓
  FAILED     FAILED       FAILED        FAILED   COMPLETED/TIMEOUT
```

## 配置参数

### PipelineTaskManager 配置

| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `check_interval` | int | 30 | 监控检查间隔(秒) |
| `timeout` | int | 3600 | 任务超时时间(秒) |

### TopicSearchProcessor 配置

| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `search_model` | str | gemini-2.0-flash-thinking-exp-01-21 | 搜索使用的LLM模型 |

## 错误处理

### 异常类型

1. **输入验证异常**
   - 缺少必要参数 (topic 或 input_file)
   - 输入文件不存在

2. **处理异常**
   - LLM API调用失败
   - 网页搜索失败
   - 爬取过程异常

3. **系统异常**
   - 数据库连接失败
   - 文件系统操作失败
   - 内存不足

### 异常处理策略

- **优雅降级**: 出现异常时更新任务状态为FAILED
- **详细日志**: 记录详细的错误信息便于调试
- **资源清理**: 确保异常情况下也能正确清理临时资源

## 性能优化

### 并发处理

1. **异步I/O**: 使用asyncio处理网络请求
2. **多线程**: 每个任务在独立线程中执行
3. **守护线程**: 避免阻塞主进程

### 资源优化

1. **临时文件管理**: 及时清理临时文件
2. **内存使用**: 流式处理大文件，避免一次性加载
3. **连接池**: 复用数据库和Redis连接

## 扩展性设计

### 处理器扩展

通过继承 `TaskProcessor` 抽象基类，可以轻松添加新的任务处理器:

```python
class CustomProcessor(TaskProcessor):
    async def process(self, task_id: str, params: Dict[str, Any]) -> Optional[str]:
        # 自定义处理逻辑
        pass
```

### 监控扩展

可以通过修改 `_check_completion_in_database` 方法来支持不同的完成检测机制。

## 依赖关系

### 内部依赖

- `src.task_manager`: Redis任务状态管理
- `src.database`: MongoDB数据存储
- `src.LLM_search`: LLM搜索功能
- `src.async_crawl`: 异步网页爬取

### 外部依赖

- `asyncio`: 异步编程支持
- `threading`: 多线程支持
- `uuid`: 唯一ID生成
- `json`: JSON数据处理

## 使用示例

### 提交主题搜索任务

```python
# 初始化任务管理器
task_manager = PipelineTaskManager(global_pipeline)

# 提交任务
task_id = task_manager.submit_task({
    'topic': '人工智能在医疗领域的应用',
    'description': '重点关注机器学习和深度学习技术',
    'top_n': 50
})

print(f"任务已提交，ID: {task_id}")
```

### 提交文件处理任务

```python
task_id = task_manager.submit_task({
    'input_file': 'data/medical_ai_papers.jsonl',
    'output_file': 'output/medical_ai_survey.jsonl'
})
```

## 总结

`pipeline_processor.py` 模块通过精心设计的架构实现了：

1. **模块化设计**: 清晰的职责分离和接口定义
2. **异步处理**: 高效的并发任务处理能力
3. **完整的生命周期管理**: 从任务提交到资源清理的全流程管理
4. **健壮的错误处理**: 全面的异常处理和状态管理
5. **良好的扩展性**: 支持新处理器类型的轻松添加

该模块是整个LLMxMapReduce系统的核心调度器，确保了系统的稳定性和可扩展性。 