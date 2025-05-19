import requests
import argparse
import json
import time
import os
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler

def setup_logging():
    # 创建日志目录
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # 设置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)
    
    # 文件处理器 (with rotation)
    log_file = os.path.join(log_dir, 'test_client.log')
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_format)
    root_logger.addHandler(file_handler)
    
    return logging.getLogger(__name__)

# 初始化日志
logger = setup_logging()

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
        'config_file': args.config_file,
    }
    
    logger.info(f"构建请求参数: {payload}")
    
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
    logger.info(f"向服务器 {args.server} 发送请求")
    try:
        response = requests.post(f"{args.server}/api/start_pipeline", json=payload)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                task_id = result['task_id']
                output_file = result['output_file']
                logger.info(f"任务提交成功! 任务ID: {task_id}, 输出文件: {output_file}")
                print(f"任务已提交成功！任务ID: {task_id}")
                print(f"输出文件将保存至: {output_file}")
                return task_id
            else:
                error = result.get('error', '未知错误')
                logger.error(f"任务提交失败: {error}")
                print(f"任务提交失败: {error}")
                return None
        else:
            logger.error(f"HTTP错误: {response.status_code}")
            print(f"HTTP错误: {response.status_code}")
            return None
    except Exception as e:
        logger.exception(f"请求异常: {str(e)}")
        print(f"请求异常: {str(e)}")
        return None

def check_task_status(server, task_id):
    logger.info(f"检查任务状态: {task_id}")
    try:
        response = requests.get(f"{server}/api/task/{task_id}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                task = result['task']
                status = task['status']
                logger.info(f"任务 {task_id} 状态: {status}")
                print(f"任务状态: {status}")
                
                if status == 'completed':
                    logger.info(f"任务 {task_id} 已完成!")
                    print(f"任务已完成！")
                    if 'execution_time' in task:
                        execution_time = task['execution_time']
                        logger.info(f"任务 {task_id} 执行时间: {execution_time}")
                        print(f"执行时间: {execution_time}")
                    if 'output_file' in task:
                        output_file = task['output_file']
                        logger.info(f"任务 {task_id} 输出文件: {output_file}")
                        print(f"输出文件: {output_file}")
                    return True
                elif status == 'failed':
                    error = task.get('error', '未知错误')
                    logger.error(f"任务 {task_id} 失败: {error}")
                    print(f"任务失败: {error}")
                    return True
                else:
                    return False
            else:
                error = result.get('error', '未知错误')
                logger.error(f"获取任务 {task_id} 状态失败: {error}")
                print(f"获取任务状态失败: {error}")
                return False
        else:
            logger.error(f"HTTP错误: {response.status_code}")
            print(f"HTTP错误: {response.status_code}")
            return False
    except Exception as e:
        logger.exception(f"检查任务状态异常: {str(e)}")
        print(f"检查任务状态异常: {str(e)}")
        return False

def main():
    args = parse_args()
    
    logger.info(f"启动测试客户端，参数: {args}")
    print(args)
    
    # 检查必需参数
    if not args.topic and not args.input_file:
        logger.error("错误: 必须提供--topic或--input_file参数")
        print("错误: 必须提供--topic或--input_file参数")
        return
    
    # 启动pipeline任务
    task_id = start_pipeline(args)
    if not task_id:
        return
    
    # 监控任务状态
    logger.info("开始监控任务状态...")
    print("开始监控任务状态...")
    completed = False
    try:
        while not completed:
            completed = check_task_status(args.server, task_id)
            if not completed:
                logger.info("等待10秒后重新检查...")
                print("等待10秒后重新检查...")
                time.sleep(10)
    except KeyboardInterrupt:
        logger.info("监控已停止，但任务仍在后台运行")
        print("\n监控已停止，但任务仍在后台运行")
        print(f"您可以稍后通过以下命令查询任务状态:")
        print(f"  curl {args.server}/api/task/{task_id}")
    
    # 如果任务完成且成功，尝试获取结果
    if completed:
        logger.info(f"尝试获取任务 {task_id} 的输出结果")
        try:
            response = requests.get(f"{args.server}/api/output/{task_id}")
            if response.status_code == 200 and response.json().get('success'):
                logger.info(f"成功获取任务 {task_id} 的输出结果")
                print("\n任务输出内容预览(前10行):")
                content = response.json()['content']
                lines = content.split("\n")
                for i, line in enumerate(lines[:10]):
                    print(f"{i+1}: {line}")
                
                if len(lines) > 10:
                    logger.info(f"任务 {task_id} 输出共 {len(lines)} 行")
                    print(f"... 共{len(lines)}行")
            else:
                error_msg = "获取输出失败" if response.status_code != 200 else response.json().get('error', '未知错误')
                logger.error(f"获取任务 {task_id} 输出失败: {error_msg}")
                print(f"获取任务输出失败: {error_msg}")
        except Exception as e:
            logger.exception(f"获取任务输出异常: {str(e)}")
            print(f"获取任务输出异常: {str(e)}")

if __name__ == "__main__":
    try:
        logger.info("启动测试客户端")
        main()
        logger.info("测试客户端执行完毕")
    except Exception as e:
        logger.exception(f"测试客户端执行异常: {str(e)}")
        print(f"执行异常: {str(e)}")