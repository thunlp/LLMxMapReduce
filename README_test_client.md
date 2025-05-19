# Web Demo测试客户端使用说明

这是一个用于测试LLMxMapReduce Web Demo API的极简命令行客户端。可以通过命令行参数控制所有关键参数。

## 前置条件

1. 确保Web Demo服务器正在运行（默认地址为`http://localhost:5000`）
2. 安装必要的Python依赖：
```
pip install requests
```

## 使用方法

### 基本用法

```bash
python test_client.py --topic "人工智能的发展"
```

此命令将使用默认配置启动一个pipeline任务，搜索主题为"人工智能的发展"，并使用服务器提供的默认配置。

### 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--server` | 服务器地址 | http://localhost:5000 |
| `--topic` | 搜索主题 | 无（必填，除非提供input_file） |
| `--description` | 主题描述 | 空字符串 |
| `--search_model` | 搜索模型 | gemini-2.0-flash-thinking-exp-01-21 |
| `--block_count` | 块数量 | 0 |
| `--data_num` | 数据数量 | 无（可选） |
| `--config_file` | 配置文件路径 | config/model_config.json |
| `--output_file` | 输出文件路径 | 自动生成 |
| `--top_n` | 检索结果数量 | 100 |
| `--input_file` | 输入文件路径（替代topic） | 无 |

### 示例

1. 使用自定义搜索模型和输出文件：

```bash
python test_client.py --topic "量子计算" --search_model "gpt-4" --output_file "output/quantum_result.jsonl"
```

2. 控制块数量和数据量：

```bash
python test_client.py --topic "气候变化" --block_count 5 --data_num 50
```

3. 使用自定义配置文件：

```bash
python test_client.py --topic "区块链技术" --config_file "my_custom_config.json"
```

4. 使用现有数据文件而非搜索：

```bash
python test_client.py --input_file "data/my_crawled_data.jsonl"
```

## 运行流程

1. 客户端将启动一个pipeline任务
2. 显示任务ID和预期输出文件路径
3. 每10秒监控一次任务状态
4. 任务完成后，显示任务执行时间和输出文件的前10行内容预览

## 中断处理

按下`Ctrl+C`可以中断监控，但任务会继续在服务器后台运行。程序会显示如何通过curl命令手动查询任务状态的方法。

## 常见问题

1. 如果遇到连接错误，请检查服务器地址和状态
2. 如果任务失败，请查看错误信息，可能需要调整参数或检查配置文件
3. 默认情况下，输出文件会保存在`output/`目录中 