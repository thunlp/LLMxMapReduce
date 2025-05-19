import os
import json
import logging
import uuid
import threading
import sys
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from src.args import parse_args
from src.decode.decode_pipeline import DecodePipeline
from src.encode.encode_pipeline import EncodePipeline
from src.hidden.hidden_pipeline import HiddenPipeline
from src.LLM_search import LLM_search
from src.async_crawl import AsyncCrawler
from async_d import Monitor, PipelineAnalyser, Pipeline
import asyncio

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# 抑制httpx和openai的日志
httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.WARNING)
openai_logger = logging.getLogger("openai")
openai_logger.setLevel(logging.WARNING)


app = Flask(__name__)
CORS(app)  

tasks = {}

class EntirePipeline(Pipeline):
    def __init__(self, 
            config_file, 
            data_num=None, 
            parallel_num=1, 
            output_each_block=False, 
            digest_group_mode="llm", 
            skeleton_group_size=3, 
            block_count=0, 
            conv_layer=6, 
            conv_kernel_width=3, 
            conv_result_num=10, 
            top_k=6,
            self_refine_count=3, 
            self_refine_best_of=3
        ):
        with open(config_file, "r") as f:
            self.config = json.load(f)

        self.parallel_num = parallel_num
        self.encode_pipeline = EncodePipeline(
            self.config["encode"], data_num
        )
        self.hidden_pipeline = HiddenPipeline(
            self.config["hidden"],
            output_each_block,
            digest_group_mode,
            skeleton_group_size,
            block_count,
            conv_layer,
            conv_kernel_width,
            conv_result_num,
            top_k,
            self_refine_count,
            self_refine_best_of,
            worker_num=self.parallel_num,
        )
        self.decode_pipeline = DecodePipeline(
            self.config["decode"], None, worker_num=self.parallel_num
        )

        all_nodes = [self.encode_pipeline, self.hidden_pipeline, self.decode_pipeline]

        super().__init__(
            all_nodes, head=self.encode_pipeline, tail=self.decode_pipeline
        )

    def _connect_nodes(self):
        self.encode_pipeline >> self.hidden_pipeline >> self.decode_pipeline
        
    def set_output_file(self, output_file):
        """设置输出文件路径"""
        if output_file is None:
            # 如果未提供输出文件路径，生成一个默认路径
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"output/result_{timestamp}.jsonl"
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            logger.info(f"未提供输出文件路径，使用默认路径: {output_file}")
        
        self.decode_pipeline.output_file = output_file


async def process_topic(topic, description, output_file, config_file, search_model, 
                       block_count, data_num, top_n, task_id):
    """处理话题搜索和爬取"""
    try:
        # 更新任务状态
        tasks[task_id]['status'] = 'searching'
        
        # 检查配置文件是否存在
        if not os.path.exists(config_file):
            raise ValueError(f"配置文件不存在: {config_file}")
        
        # 获取检索查询
        logger.info(f"[任务 {task_id}] 开始生成查询")
        retriever = LLM_search(model=search_model, infer_type="OpenAI", engine='google', each_query_result=10)
        queries = retriever.get_queries(topic=topic, description=description)
        
        # 更新任务状态
        tasks[task_id]['status'] = 'searching_web'
        logger.info(f"[任务 {task_id}] 开始搜索页面")
        
        # 搜索网页
        url_list = retriever.batch_web_search(queries=queries, topic=topic, top_n=int(top_n * 1.2))
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 准备爬取输出路径
        tasks[task_id]['status'] = 'crawling'
        crawl_output_path = f"output/{topic}_{timestamp}_crawl_result.jsonl"
        os.makedirs(os.path.dirname(crawl_output_path), exist_ok=True)
        
        # 爬取内容
        logger.info(f"[任务 {task_id}] 开始爬取网页内容")
        crawler = AsyncCrawler(model=search_model, infer_type="OpenAI")
        await crawler.run(
            topic=topic,
            url_list=url_list,
            crawl_output_file_path=crawl_output_path,
            top_n=top_n
        )
        
        # 启动管道处理
        logger.info(f"[任务 {task_id}] 爬取完成，开始处理管道")
        
        # 运行管道
        return crawl_output_path
    except Exception as e:
        logger.error(f"[任务 {task_id}] 处理话题失败: {str(e)}")
        # 不直接抛出异常，而是返回None并在调用者处理
        return None


def run_pipeline_task(task_id, params):
    """后台运行管道任务"""
    try:
        # 记录开始时间
        start_time = datetime.now()
        tasks[task_id]['start_time'] = start_time.strftime('%Y-%m-%d %H:%M:%S')
        
        # 初始化参数，与args.py保持一致的默认值
        topic = params.get('topic')
        description = params.get('description', '')
        output_file = params.get('output_file')
        config_file = params.get('config_file', 'config/model_config.json')  # 使用正斜杠
        search_model = params.get('search_model', 'gemini-2.0-flash-thinking-exp-01-21')  
        block_count = int(params.get('block_count', 0))  
        data_num = params.get('data_num', None) 
        top_n = int(params.get('top_n', 100))
        input_file = params.get('input_file')
        
        # 高级参数
        parallel_num = int(params.get('parallel_num', 1))
        output_each_block = bool(params.get('output_each_block', False))
        digest_group_mode = params.get('digest_group_mode', 'llm')
        skeleton_group_size = int(params.get('skeleton_group_size', 3))
        conv_layer = int(params.get('conv_layer', 6))
        conv_kernel_width = int(params.get('conv_kernel_width', 3))
        conv_result_num = int(params.get('conv_result_num', 10))
        top_k = int(params.get('top_k', 6))
        self_refine_count = int(params.get('self_refine_count', 3))
        self_refine_best_of = int(params.get('self_refine_best_of', 3))
        
        # 修正config_file路径中的分隔符，确保跨平台兼容性
        config_file = config_file.replace('\\', os.path.sep)
        
        # 确保配置文件存在
        if not os.path.exists(config_file):
            # 尝试从不同相对路径查找配置文件
            possible_paths = [
                config_file,
                os.path.join(os.path.dirname(os.path.abspath(__file__)), config_file),
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), config_file)
            ]
            
            found = False
            for path in possible_paths:
                if os.path.exists(path):
                    config_file = path
                    found = True
                    logger.info(f"找到配置文件: {config_file}")
                    break
            
            if not found:
                raise ValueError(f"找不到配置文件: {config_file}")
        
        # 确保输出目录存在
        if output_file:
            output_dir = os.path.dirname(output_file)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
        
        # 创建并启动管道
        pipeline = EntirePipeline(
            config_file=config_file,
            data_num=data_num,
            parallel_num=parallel_num,
            output_each_block=output_each_block,
            digest_group_mode=digest_group_mode,
            skeleton_group_size=skeleton_group_size,
            block_count=block_count,
            conv_layer=conv_layer,
            conv_kernel_width=conv_kernel_width,
            conv_result_num=conv_result_num,
            top_k=top_k,
            self_refine_count=self_refine_count,
            self_refine_best_of=self_refine_best_of
        )
        
        # 设置输出文件
        pipeline.set_output_file(output_file)
        
        # 配置分析器和监控器
        pipeline_analyser = PipelineAnalyser()
        pipeline_analyser.register(pipeline)
        
        monitor = Monitor(report_interval=60)
        monitor.register(pipeline_analyser)
        monitor.start()
        
        # 启动管道
        pipeline.start()
        
        if topic:
            # 如果指定了主题，先进行检索和爬取
            tasks[task_id]['status'] = 'preparing'
            logger.info(f"[任务 {task_id}] 开始处理主题: {topic}")
            
            # 创建output目录
            os.makedirs("output", exist_ok=True)
            
            # 使用asyncio来运行异步函数
            crawl_output_path = asyncio.run(
                process_topic(
                    topic=topic,
                    description=description,
                    output_file=output_file,
                    config_file=config_file,
                    search_model=search_model,
                    block_count=block_count,
                    data_num=data_num,
                    top_n=top_n,
                    task_id=task_id
                )
            )
            
            # 检查crawl_output_path是否为None（表示处理过程中出现错误）
            if crawl_output_path is None:
                raise ValueError(f"处理主题'{topic}'时出现错误，无法获取爬取结果")
            
            # 更新任务状态
            tasks[task_id]['status'] = 'processing'
            # 将爬取结果输入管道
            pipeline.put(crawl_output_path)
        elif input_file:
            # 如果指定了输入文件
            if not os.path.exists(input_file):
                raise ValueError(f"输入文件不存在: {input_file}")
                
            tasks[task_id]['status'] = 'processing'
            logger.info(f"[任务 {task_id}] 开始处理输入文件: {input_file}")
            pipeline.put(input_file)
        else:
            raise ValueError("必须指定topic或input_file参数")
        
        # 记录结束时间
        end_time = datetime.now()
        tasks[task_id]['end_time'] = end_time.strftime('%Y-%m-%d %H:%M:%S')
        
        # 计算执行时间
        execution_time = end_time - start_time
        tasks[task_id]['execution_time'] = str(execution_time)
        tasks[task_id]['execution_seconds'] = execution_time.total_seconds()
        
        # 任务完成
        tasks[task_id]['status'] = 'completed'
        tasks[task_id]['output_file'] = output_file
        logger.info(f"[任务 {task_id}] 任务已完成，执行时间: {execution_time}")
        
    except Exception as e:
        # 记录完整的异常堆栈信息
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(f"[任务 {task_id}] 执行任务失败，完整堆栈信息:\n{error_traceback}")
        # 记录结束时间（即使失败）
        end_time = datetime.now()
        tasks[task_id]['end_time'] = end_time.strftime('%Y-%m-%d %H:%M:%S')
        
        # 计算执行时间
        if 'start_time' in tasks[task_id]:
            start_time = datetime.strptime(tasks[task_id]['start_time'], '%Y-%m-%d %H:%M:%S')
            execution_time = end_time - start_time
            tasks[task_id]['execution_time'] = str(execution_time)
            tasks[task_id]['execution_seconds'] = execution_time.total_seconds()
        
        logger.error(f"[任务 {task_id}] 执行任务失败: {str(e)}")
        tasks[task_id]['status'] = 'failed'
        tasks[task_id]['error'] = str(e)


@app.route('/api/start_pipeline', methods=['POST'])
def start_pipeline():
    """API接口启动pipeline任务"""
    try:
        # 获取请求参数
        data = request.json
        
        # 生成任务ID
        task_id = str(uuid.uuid4())
        
        # 生成时间戳
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 准备输出文件路径（如果未提供）
        if 'output_file' not in data or not data['output_file']:
            topic = data.get('topic', 'output')
            data['output_file'] = f"output/{topic}_{timestamp}_result.jsonl"
            
            # 确保输出目录存在
            os.makedirs('output', exist_ok=True)
        
        # 创建任务记录
        tasks[task_id] = {
            'id': task_id,
            'status': 'pending',
            'created_at': timestamp,
            'params': data
        }
        
        # 启动后台线程运行pipeline
        thread = threading.Thread(
            target=run_pipeline_task,
            args=(task_id, data)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': '任务已提交',
            'output_file': data['output_file']
        })
    
    except Exception as e:
        logger.exception("启动pipeline失败")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/task/<task_id>', methods=['GET'])
def get_task_status(task_id):
    """获取任务状态"""
    if task_id not in tasks:
        return jsonify({
            'success': False,
            'error': '任务不存在'
        }), 404
    
    task = tasks[task_id]
    return jsonify({
        'success': True,
        'task': task
    })


@app.route('/api/tasks', methods=['GET'])
def get_all_tasks():
    """获取所有任务"""
    return jsonify({
        'success': True,
        'tasks': list(tasks.values())
    })


@app.route('/api/output/<task_id>', methods=['GET'])
def get_task_output(task_id):
    """获取任务输出结果"""
    if task_id not in tasks:
        return jsonify({
            'success': False,
            'error': '任务不存在'
        }), 404
    
    task = tasks[task_id]
    
    if task['status'] != 'completed':
        return jsonify({
            'success': False,
            'error': f"任务尚未完成，当前状态：{task['status']}"
        }), 400
    
    output_file = task.get('output_file')
    if not output_file or not os.path.exists(output_file):
        return jsonify({
            'success': False,
            'error': '输出文件不存在'
        }), 404
    
    try:
        with open(output_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return jsonify({
            'success': True,
            'content': content
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f"读取输出文件失败: {str(e)}"
        }), 500


if __name__ == '__main__':
    # 设置环境变量
    os.environ['PYTHONPATH'] = f"{os.getcwd()}:{os.environ.get('PYTHONPATH', '')}"
    os.environ['PROMPT_LANGUAGE'] = "zh"
    os.environ['OPENAI_API_KEY'] = "8fe0e1fa-3fb5-4d82-b73e-7eb21480628a"
    os.environ['OPENAI_API_BASE'] = "https://ark.cn-beijing.volces.com/api/v3"
    os.environ['SERPER_API_KEY'] = "769aed5f5ca7b1ad747d71b57224eb53135d0069"
    
    # 启动Flask应用
    app.run(host='0.0.0.0', port=5000, debug=True) 