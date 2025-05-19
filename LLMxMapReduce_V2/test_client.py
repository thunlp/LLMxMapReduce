import requests
import argparse
import json
import time
import os
from datetime import datetime

def parse_args():
    parser = argparse.ArgumentParser(description='Web Demo客户端测试工具')
    parser.add_argument('--server', type=str, default='http://localhost:5000', help='服务器地址')
    parser.add_argument('--topic', type=str, help='搜索主题')
    parser.add_argument('--description', type=str, default='', help='主题描述')
    parser.add_argument('--search_model', type=str, default='gemini-2.0-flash-thinking-exp-01-21', help='搜索模型')
    parser.add_argument('--block_count', type=int, default=0, help='块数量')
    parser.add_argument('--data_num', type=str, help='数据数量，可选')
    parser.add_argument('--config_file', type=str, default='config/model_config.json', help='配置文件路径')
    parser.add_argument('--output_file', type=str, help='输出文件路径')
    parser.add_argument('--top_n', type=int, default=100, help='检索结果数量')
    parser.add_argument('--input_file', type=str, help='输入文件路径（替代topic）')
    return parser.parse_args()

def start_pipeline(args):
    # 构建请求参数
    payload = {
        'topic': args.topic,
        'description': args.description,
        'search_model': args.search_model,
        'block_count': args.block_count,
        'top_n': args.top_n,
        'config_file': args.config_file
    }
    
    # 添加可选参数
    if args.data_num is not None:
        payload['data_num'] = args.data_num
    
    if args.output_file:
        payload['output_file'] = args.output_file
    else:
        # 生成默认输出文件路径
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        topic = args.topic or 'output'
        payload['output_file'] = f"output/{topic}_{timestamp}_result.jsonl"
    
    # 如果提供了input_file则使用它代替topic
    if args.input_file:
        payload['input_file'] = args.input_file
        # 如果同时提供了topic和input_file，移除topic
        if 'topic' in payload:
            del payload['topic']
    
    # 发送请求
    response = requests.post(f"{args.server}/api/start_pipeline", json=payload)
    
    if response.status_code == 200:
        result = response.json()
        if result.get('success'):
            print(f"任务已提交成功！任务ID: {result['task_id']}")
            print(f"输出文件将保存至: {result['output_file']}")
            return result['task_id']
        else:
            print(f"任务提交失败: {result.get('error', '未知错误')}")
            return None
    else:
        print(f"HTTP错误: {response.status_code}")
        return None

def check_task_status(server, task_id):
    response = requests.get(f"{server}/api/task/{task_id}")
    
    if response.status_code == 200:
        result = response.json()
        if result.get('success'):
            task = result['task']
            status = task['status']
            print(f"任务状态: {status}")
            
            if status == 'completed':
                print(f"任务已完成！")
                if 'execution_time' in task:
                    print(f"执行时间: {task['execution_time']}")
                if 'output_file' in task:
                    print(f"输出文件: {task['output_file']}")
                return True
            elif status == 'failed':
                print(f"任务失败: {task.get('error', '未知错误')}")
                return True
            else:
                return False
        else:
            print(f"获取任务状态失败: {result.get('error', '未知错误')}")
            return False
    else:
        print(f"HTTP错误: {response.status_code}")
        return False

def main():
    args = parse_args()
    
    # 检查必需参数
    if not args.topic and not args.input_file:
        print("错误: 必须提供--topic或--input_file参数")
        return
    
    # 启动pipeline任务
    task_id = start_pipeline(args)
    if not task_id:
        return
    
    # 监控任务状态
    print("开始监控任务状态...")
    completed = False
    try:
        while not completed:
            completed = check_task_status(args.server, task_id)
            if not completed:
                print("等待10秒后重新检查...")
                time.sleep(10)
    except KeyboardInterrupt:
        print("\n监控已停止，但任务仍在后台运行")
        print(f"您可以稍后通过以下命令查询任务状态:")
        print(f"  curl {args.server}/api/task/{task_id}")
    
    # 如果任务完成且成功，尝试获取结果
    if completed:
        response = requests.get(f"{args.server}/api/output/{task_id}")
        if response.status_code == 200 and response.json().get('success'):
            print("\n任务输出内容预览(前10行):")
            content = response.json()['content']
            lines = content.split("\n")
            for i, line in enumerate(lines[:10]):
                print(f"{i+1}: {line}")
            
            if len(lines) > 10:
                print(f"... 共{len(lines)}行")

if __name__ == "__main__":
    main() 