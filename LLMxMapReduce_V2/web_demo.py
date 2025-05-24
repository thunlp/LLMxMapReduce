import os
import json
import logging
import uuid
import threading
import sys
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from flask import Flask, request, jsonify
from flask_cors import CORS
import glob

"""
LLMxMapReduce Web演示服务 - 数据库优化版本

架构说明：
1. 使用全局唯一的pipeline实例，避免重复创建
2. 使用MongoDB存储survey结果，替代文件存储
3. 基于task_id的高效结果查询，消除文件扫描瓶颈
4. 支持真正的并发处理，提供生产级性能
5. 保持文件存储作为备选方案，确保向后兼容性

数据库优势：
- O(1)复杂度的结果查询（基于索引）
- 并发安全的写入操作
- 更好的容错和恢复能力
- 便于数据管理和统计

API接口：
- POST /api/start_pipeline: 启动新任务
- GET /api/task/<task_id>: 获取任务状态  
- GET /api/task/<task_id>/pipeline_status: 获取任务相关的pipeline状态
- GET /api/global_pipeline_status: 获取全局pipeline状态
- GET /api/tasks: 获取所有任务列表
- GET /api/output/<task_id>: 获取任务输出结果
- GET /api/database/stats: 获取数据库统计信息
- GET /api/database/health: 数据库健康检查
"""

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from src.decode.decode_pipeline import DecodePipeline
from src.encode.encode_pipeline import EncodePipeline
from src.hidden.hidden_pipeline import HiddenPipeline
from src.LLM_search import LLM_search
from src.async_crawl import AsyncCrawler
from async_d import Monitor, PipelineAnalyser, Pipeline
import asyncio

# 配置日志
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
    log_file = os.path.join(log_dir, 'web_demo.log')
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_format)
    root_logger.addHandler(file_handler)
    
    # 抑制httpx和openai的日志
    httpx_logger = logging.getLogger("httpx")
    httpx_logger.setLevel(logging.WARNING)
    openai_logger = logging.getLogger("openai")
    openai_logger.setLevel(logging.WARNING)
    
    return logging.getLogger(__name__)

# 初始化日志
logger = setup_logging()

# 导入数据库支持
try:
    from src.database import mongo_manager
    DATABASE_AVAILABLE = True
    logger.info("数据库模块加载成功")
except ImportError as e:
    DATABASE_AVAILABLE = False
    logger.warning(f"数据库模块不可用，将仅使用文件存储: {str(e)}")

# 全局pipeline实例和相关变量
global_pipeline = None
pipeline_monitor = None
# 保留文件存储作为备选方案
global_output_file = "output/global_pipeline_output.jsonl"

app = Flask(__name__)
CORS(app)  

# todo add Redis
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
            self_refine_best_of=3,
            use_database=True,
            fallback_output_file=None
        ):
        with open(config_file, "r") as f:
            self.config = json.load(f)

        self.parallel_num = parallel_num
        self.use_database = use_database and DATABASE_AVAILABLE
        self.fallback_output_file = fallback_output_file
        
        self.encode_pipeline = EncodePipeline(
            self.config["encode"], 
            int(data_num) if data_num is not None else None
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
        
        # 创建decode_pipeline，支持数据库存储
        self.decode_pipeline = DecodePipeline(
            self.config["decode"], 
            output_file=self.fallback_output_file,  # 作为备选方案
            worker_num=self.parallel_num,
            use_database=self.use_database
        )

        all_nodes = [self.encode_pipeline, self.hidden_pipeline, self.decode_pipeline]

        super().__init__(
            all_nodes, head=self.encode_pipeline, tail=self.decode_pipeline
        )
        
        logger.info(f"EntirePipeline初始化完成: 数据库存储={'启用' if self.use_database else '禁用'}")

    def _connect_nodes(self):
        self.encode_pipeline >> self.hidden_pipeline >> self.decode_pipeline
        
    def set_output_file(self, output_file):
        """设置备用输出文件路径（向后兼容）"""
        if output_file is None:
            # 如果未提供输出文件路径，生成一个默认路径
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"output/result_{timestamp}.jsonl"
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            logger.info(f"未提供输出文件路径，使用默认路径: {output_file}")
        
        self.fallback_output_file = output_file
        self.decode_pipeline.set_output_file(output_file)


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


def init_global_pipeline():
    """初始化全局pipeline（数据库优先模式）"""
    global global_pipeline, pipeline_monitor
    
    if global_pipeline is None:
        logger.info("正在初始化全局pipeline（数据库优先模式）...")
        
        # 初始化数据库连接
        if DATABASE_AVAILABLE:
            try:
                if mongo_manager.connect():
                    logger.info("数据库连接成功，将使用数据库存储")
                else:
                    logger.warning("数据库连接失败，将使用文件存储作为备选方案")
            except Exception as e:
                logger.warning(f"数据库初始化失败，将使用文件存储作为备选方案: {str(e)}")
        else:
            logger.info("数据库模块不可用，将使用文件存储")
        
        # 使用默认配置
        config_file = '/home/ubuntu/projects/dev/LLMxMapReduce/LLMxMapReduce_V2/config/model_config_ds.json'  
        
        # 确保配置文件存在
        if not os.path.exists(config_file):
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
        
        # 确保全局输出目录存在（文件存储备选方案）
        os.makedirs(os.path.dirname(global_output_file), exist_ok=True)
        
        # 创建全局pipeline实例，优先使用数据库存储
        global_pipeline = EntirePipeline(
            config_file=config_file,
            data_num=1,
            parallel_num=3,
            output_each_block=False,
            digest_group_mode='llm',
            skeleton_group_size=3,
            block_count=1,
            conv_layer=6,
            conv_kernel_width=3,
            conv_result_num=10,
            top_k=6,
            self_refine_count=3,
            self_refine_best_of=3,
            use_database=DATABASE_AVAILABLE,  # 根据数据库可用性决定
            fallback_output_file=global_output_file  # 备选文件输出
        )
        
        # 配置分析器和监控器
        pipeline_analyser = PipelineAnalyser()
        pipeline_analyser.register(global_pipeline)
        
        pipeline_monitor = Monitor(report_interval=60)
        pipeline_monitor.register(pipeline_analyser)
        pipeline_monitor.start()
        
        # 启动pipeline
        global_pipeline.start()
        
        # 记录启动信息
        storage_mode = "数据库存储" if DATABASE_AVAILABLE else "文件存储"
        logger.info(f"全局pipeline已启动并正在运行")
        logger.info(f"存储模式: {storage_mode}")
        if not DATABASE_AVAILABLE:
            logger.info(f"备选输出文件: {global_output_file}")
        
        # 输出数据库状态信息
        if DATABASE_AVAILABLE:
            try:
                stats = mongo_manager.get_stats()
                logger.info(f"数据库状态: 共有 {stats['total_surveys']} 个综述记录，成功率: {stats['success_rate']:.2%}")
            except Exception as e:
                logger.warning(f"无法获取数据库状态: {str(e)}")


def extract_task_results(task_id, final_output_file):
    """从全局输出文件中提取特定任务的结果"""
    try:
        if not os.path.exists(global_output_file):
            logger.warning(f"[任务 {task_id}] 全局输出文件不存在: {global_output_file}")
            return False
        
        # 创建最终输出文件的目录
        os.makedirs(os.path.dirname(final_output_file), exist_ok=True)
        
        # 获取任务的期望标题
        expected_title = tasks[task_id].get('expected_survey_title')
        if not expected_title:
            logger.warning(f"[任务 {task_id}] 未找到任务的期望综述标题")
            return False
        
        # 读取全局输出文件，查找包含特定标题的记录
        task_results = []
        with open(global_output_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    record = json.loads(line.strip())
                    # 检查记录标题是否匹配当前任务的期望标题
                    if record.get('title') == expected_title:
                        task_results.append(line)
                        logger.info(f"[任务 {task_id}] 找到匹配的综述记录: {expected_title}")
                except json.JSONDecodeError:
                    continue
        
        if task_results:
            # 将结果写入最终输出文件
            with open(final_output_file, 'w', encoding='utf-8') as f:
                f.writelines(task_results)  # 写入所有匹配的记录
            
            logger.info(f"[任务 {task_id}] 已提取 {len(task_results)} 条记录到: {final_output_file}")
            return True
        else:
            logger.warning(f"[任务 {task_id}] 未找到标题为 '{expected_title}' 的综述记录")
            return False
            
    except Exception as e:
        logger.error(f"[任务 {task_id}] 提取任务结果失败: {str(e)}")
        return False


def check_survey_completed_in_database(task_id):
    """从数据库检查任务是否完成"""
    try:
        if not DATABASE_AVAILABLE:
            return False
        
        survey_record = mongo_manager.get_survey(task_id)
        if survey_record and survey_record.get('status') == 'completed':
            logger.info(f"[任务 {task_id}] 在数据库中找到已完成的综述")
            return True
        
        return False
    except Exception as e:
        logger.error(f"[任务 {task_id}] 数据库查询失败: {str(e)}")
        return False


def start_task_monitoring_database(task_id):
    """启动数据库模式的任务监控"""
    def monitor_task():
        logger.info(f"[任务 {task_id}] 开始监控任务完成状态（数据库模式）")
        
        start_monitor_time = time.time()
        check_interval = 30  # 30秒检查间隔（数据库查询更高效）
        timeout = 3600  # 1小时超时
        
        while time.time() - start_monitor_time < timeout:
            # 检查数据库中是否存在已完成的任务
            if check_survey_completed_in_database(task_id):
                logger.info(f"[任务 {task_id}] 检测到任务已完成")
                break
            
            logger.debug(f"[任务 {task_id}] 任务尚未完成，继续等待...")
            time.sleep(check_interval)
        else:
            # 超时
            logger.warning(f"[任务 {task_id}] 监控超时，任务可能未完成")
        
        # 清理临时文件
        try:
            temp_files = glob.glob(f"*.{task_id}.tmp")
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    logger.info(f"[任务 {task_id}] 已清理临时文件: {temp_file}")
        except Exception as e:
            logger.warning(f"[任务 {task_id}] 清理临时文件时出现错误: {str(e)}")
        
        # 更新任务状态
        end_time = datetime.now()
        if 'start_time' in tasks[task_id]:
            start_time = datetime.strptime(tasks[task_id]['start_time'], '%Y-%m-%d %H:%M:%S')
            execution_time = end_time - start_time
            tasks[task_id]['execution_time'] = str(execution_time)
            tasks[task_id]['execution_seconds'] = execution_time.total_seconds()
        
        tasks[task_id]['end_time'] = end_time.strftime('%Y-%m-%d %H:%M:%S')
        
        if check_survey_completed_in_database(task_id):
            tasks[task_id]['status'] = 'completed'
            logger.info(f"[任务 {task_id}] 任务已完成，执行时间: {tasks[task_id].get('execution_time', 'unknown')}")
        else:
            tasks[task_id]['status'] = 'failed'
            tasks[task_id]['error'] = '任务超时或处理失败'
            logger.error(f"[任务 {task_id}] 任务处理超时或失败")
    
    # 启动监控线程
    monitor_thread = threading.Thread(target=monitor_task)
    monitor_thread.daemon = True
    monitor_thread.start()


def check_survey_exists_in_file(expected_title, file_path):
    """检查文件中是否存在指定标题的综述（备选方案）"""
    try:
        if not os.path.exists(file_path):
            return False
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    record = json.loads(line.strip())
                    if record.get('title') == expected_title:
                        return True
                except json.JSONDecodeError:
                    continue
        return False
    except Exception:
        return False


def start_task_monitoring_with_extraction(task_id, final_output_file):
    """启动任务监控线程，包含结果提取功能（基于内容检测）- 文件模式备选方案"""
    def monitor_task():
        logger.info(f"[任务 {task_id}] 开始监控全局输出文件: {global_output_file}")
        
        # 获取任务的期望标题
        expected_title = tasks[task_id].get('expected_survey_title')
        if not expected_title:
            logger.error(f"[任务 {task_id}] 未找到任务的期望综述标题，无法监控")
            tasks[task_id]['status'] = 'failed'
            tasks[task_id]['error'] = '缺少期望综述标题'
            return
        
        start_monitor_time = time.time()
        check_interval = 600  # 检查间隔（秒）
        timeout = 3600  # 1小时超时
        
        logger.info(f"[任务 {task_id}] 开始检查标题为 '{expected_title}' 的综述是否完成")
        
        while time.time() - start_monitor_time < timeout:
            # 检查文件中是否存在期望的综述
            if check_survey_exists_in_file(expected_title, global_output_file):
                logger.info(f"[任务 {task_id}] 检测到期望的综述已完成: {expected_title}")
                break
            
            logger.debug(f"[任务 {task_id}] 尚未找到期望的综述，继续等待...")
            time.sleep(check_interval)
        else:
            # 超时
            logger.warning(f"[任务 {task_id}] 监控超时，未找到期望的综述: {expected_title}")
        
        # 提取任务结果
        task_completed = extract_task_results(task_id, final_output_file)
        
        # 清理临时文件
        try:
            temp_files = glob.glob(f"*.{task_id}.tmp")
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    logger.info(f"[任务 {task_id}] 已清理临时文件: {temp_file}")
        except Exception as e:
            logger.warning(f"[任务 {task_id}] 清理临时文件时出现错误: {str(e)}")
        
        if task_completed:
            # 任务完成
            end_time = datetime.now()
            if 'start_time' in tasks[task_id]:
                start_time = datetime.strptime(tasks[task_id]['start_time'], '%Y-%m-%d %H:%M:%S')
                execution_time = end_time - start_time
                tasks[task_id]['execution_time'] = str(execution_time)
                tasks[task_id]['execution_seconds'] = execution_time.total_seconds()
            
            tasks[task_id]['end_time'] = end_time.strftime('%Y-%m-%d %H:%M:%S')
            tasks[task_id]['status'] = 'completed'
            tasks[task_id]['output_file'] = final_output_file
            logger.info(f"[任务 {task_id}] 任务已完成，执行时间: {tasks[task_id].get('execution_time', 'unknown')}")
        else:
            # 任务失败
            end_time = datetime.now()
            if 'start_time' in tasks[task_id]:
                start_time = datetime.strptime(tasks[task_id]['start_time'], '%Y-%m-%d %H:%M:%S')
                execution_time = end_time - start_time
                tasks[task_id]['execution_time'] = str(execution_time)
                tasks[task_id]['execution_seconds'] = execution_time.total_seconds()
            
            tasks[task_id]['end_time'] = end_time.strftime('%Y-%m-%d %H:%M:%S')
            tasks[task_id]['status'] = 'failed'
            tasks[task_id]['error'] = '提取任务结果失败或超时'
            logger.error(f"[任务 {task_id}] 任务处理失败或超时")
    
    # 启动监控线程
    monitor_thread = threading.Thread(target=monitor_task)
    monitor_thread.daemon = True
    monitor_thread.start()


def modify_input_file_with_unique_title(input_file_path, unique_title, task_id):
    """修改输入文件，添加task_id和唯一标题"""
    try:
        # 读取原始文件
        with open(input_file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 创建临时文件路径
        temp_file_path = f"{input_file_path}.{task_id}.tmp"
        
        # 修改每一行的title字段并添加task_id
        with open(temp_file_path, 'w', encoding='utf-8') as f:
            for line in lines:
                try:
                    data = json.loads(line.strip())
                    if 'title' in data:
                        original_title = data['title']
                        data['title'] = unique_title
                        data['task_id'] = task_id  # 添加task_id字段
                        logger.info(f"[任务 {task_id}] 将Survey标题从 '{original_title}' 修改为 '{unique_title}'，添加task_id")
                    f.write(json.dumps(data, ensure_ascii=False) + '\n')
                except json.JSONDecodeError:
                    # 如果无法解析JSON，保持原样
                    f.write(line)
        
        logger.info(f"[任务 {task_id}] 已创建修改后的输入文件: {temp_file_path}")
        return temp_file_path
        
    except Exception as e:
        logger.error(f"[任务 {task_id}] 修改输入文件失败: {str(e)}")
        return input_file_path  # 如果修改失败，返回原始文件路径


def run_pipeline_task(task_id, params):
    """后台运行管道任务（使用全局pipeline流水线方式）"""
    try:
        # 确保全局pipeline已初始化
        init_global_pipeline()
        
        logger.info(f"[任务 {task_id}] 开始执行（流水线模式）")
        
        # 记录开始时间
        start_time = datetime.now()
        tasks[task_id]['start_time'] = start_time.strftime('%Y-%m-%d %H:%M:%S')
        
        # 获取唯一的综述标题
        unique_survey_title = tasks[task_id].get('expected_survey_title')
        if not unique_survey_title:
            raise ValueError(f"[任务 {task_id}] 缺少期望的综述标题")
        
        # 解析参数
        topic = params.get('topic')
        description = params.get('description', '')
        output_file = params.get('output_file')
        config_file = params.get('config_file', 'config/model_config.json')
        search_model = params.get('search_model', 'gemini-2.0-flash-thinking-exp-01-21')
        block_count = int(params.get('block_count', 0))
        data_num = params.get('data_num', None)
        if data_num is not None:
            data_num = int(data_num)
        top_n = int(params.get('top_n', 100))
        input_file = params.get('input_file')
        
        # 确保输出目录存在
        if output_file:
            output_dir = os.path.dirname(output_file)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
        
        # 删除旧的输出文件（如果存在）
        if os.path.exists(output_file):
            os.remove(output_file)
            logger.info(f"[任务 {task_id}] 删除旧的输出文件")
        
        input_file_path = None
        
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
            
            if crawl_output_path is None:
                raise ValueError(f"处理主题'{topic}'时出现错误，无法获取爬取结果")
            
            input_file_path = crawl_output_path
            
        elif input_file:
            if not os.path.exists(input_file):
                raise ValueError(f"输入文件不存在: {input_file}")
            
            input_file_path = input_file
            logger.info(f"[任务 {task_id}] 使用输入文件: {input_file}")
            
        else:
            raise ValueError("必须指定topic或input_file参数")
        
        # 修改输入文件中的标题为唯一标题
        modified_input_file = modify_input_file_with_unique_title(input_file_path, unique_survey_title, task_id)
        
        # 更新任务状态为处理中
        tasks[task_id]['status'] = 'processing'
        logger.info(f"[任务 {task_id}] 将修改后的数据输入全局pipeline: {modified_input_file}")
        
        # 启动任务监控（必须在put之前启动）
        start_task_monitoring_database(task_id)
        
        # 将修改后的数据输入全局pipeline（非阻塞）
        global_pipeline.put(modified_input_file)
        
        logger.info(f"[任务 {task_id}] 数据已提交到pipeline，启动后台监控")
        
        # 任务提交完成，不等待处理结果
        
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
        
        logger.info(f"收到pipeline请求: {data}")
        
        # 生成任务ID
        task_id = str(uuid.uuid4())
        
        # 生成时间戳
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 获取原始topic并生成唯一的综述标题
        original_topic = data.get('topic', 'unnamed_survey')
        unique_survey_title = f"{original_topic}_{task_id}_{timestamp}"
        
        # 准备输出文件路径（如果未提供）
        if 'output_file' not in data or not data['output_file']:
            data['output_file'] = f"output/{original_topic}_{timestamp}_result.jsonl"
            
            # 确保输出目录存在
            os.makedirs('output', exist_ok=True)
        
        # 创建任务记录，包含期望的综述标题
        tasks[task_id] = {
            'id': task_id,
            'status': 'pending',
            'created_at': timestamp,
            'params': data,
            'original_topic': original_topic,
            'expected_survey_title': unique_survey_title
        }
        
        logger.info(f"[任务 {task_id}] 生成唯一综述标题: {unique_survey_title}")
        
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
            'output_file': data['output_file'],
            'original_topic': original_topic,
            'unique_survey_title': unique_survey_title
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
    task_info = {}
    for key, value in task.items():
        if key != 'pipeline':  # 排除pipeline对象，因为pipeline对象不可序列化
            task_info[key] = value
    
    return jsonify({
        'success': True,
        'task': task_info
    })



@app.route('/api/task/<task_id>/pipeline_status', methods=['GET'])
def get_pipeline_status(task_id):
    """获取pipeline详细状态（使用全局pipeline）"""
    if task_id not in tasks:
        return jsonify({
            'success': False,
            'error': '任务不存在'
        }), 404
    
    task = tasks[task_id]
    
    # 构建基本响应
    response = {
        'success': True,
        'task_id': task_id,
        'status': task['status'],
        'pipeline_running': False,
        'nodes': [],
        'is_global_pipeline': True
    }
    
    # 如果全局pipeline存在，获取详细状态
    if global_pipeline is not None:
        response['pipeline_running'] = global_pipeline.is_start
        
        # 获取各个节点的状态
        for node_name, node in global_pipeline.all_nodes.items():
            node_info = {
                'name': node_name,
                'is_running': node.is_start,
                'status': '运行中' if node.is_start else '已完成'
            }
            
            # 如果是Node类型，添加更多详细信息
            if hasattr(node, 'src_queue'):
                node_info.update({
                    'queue_size': node.src_queue.qsize(),
                    'max_queue_size': node.src_queue.maxsize,
                    'executing_count': len(node.executing_data_queue) if hasattr(node, 'executing_data_queue') else 0,
                    'worker_count': getattr(node, 'worker_num', 0)
                })
            
            response['nodes'].append(node_info)
    else:
        response['pipeline_running'] = False
        response['nodes'] = []
    
    return jsonify(response)


@app.route('/api/global_pipeline_status', methods=['GET'])
def get_global_pipeline_status():
    """获取全局pipeline状态"""
    response = {
        'success': True,
        'pipeline_initialized': global_pipeline is not None,
        'pipeline_running': False,
        'nodes': [],
        'active_tasks_count': len([task for task in tasks.values() if task['status'] in ['pending', 'preparing', 'searching', 'searching_web', 'crawling', 'processing']]),
        'total_tasks_count': len(tasks)
    }
    
    # 如果全局pipeline存在，获取详细状态
    if global_pipeline is not None:
        response['pipeline_running'] = global_pipeline.is_start
        
        # 获取各个节点的状态
        for node_name, node in global_pipeline.all_nodes.items():
            node_info = {
                'name': node_name,
                'is_running': node.is_start,
                'status': '运行中' if node.is_start else '已完成'
            }
            
            # 如果是Node类型，添加更多详细信息
            if hasattr(node, 'src_queue'):
                node_info.update({
                    'queue_size': node.src_queue.qsize(),
                    'max_queue_size': node.src_queue.maxsize,
                    'executing_count': len(node.executing_data_queue) if hasattr(node, 'executing_data_queue') else 0,
                    'worker_count': getattr(node, 'worker_num', 0)
                })
            
            response['nodes'].append(node_info)
    
    return jsonify(response)


@app.route('/api/tasks', methods=['GET'])
def get_all_tasks():
    """获取所有任务"""
    tasks_infos = []
    for task in tasks.values():
        task_info = {}
        for key, value in task.items():
            if key != 'pipeline':  # 排除pipeline对象
                task_info[key] = value
        tasks_infos.append(task_info)

    return jsonify({
        'success': True,
        'tasks': tasks_infos,
        'global_pipeline_mode': True
    })


@app.route('/api/output/<task_id>', methods=['GET'])
def get_task_output(task_id):
    """获取任务输出结果 - 数据库优先，文件备选"""
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
    
    # 优先尝试从数据库获取结果
    if DATABASE_AVAILABLE:
        try:
            survey_record = mongo_manager.get_survey(task_id)
            if survey_record and survey_record.get('survey_data'):
                logger.info(f"从数据库获取任务结果: {task_id}")
                return jsonify({
                    'success': True,
                    'content': json.dumps(survey_record['survey_data'], ensure_ascii=False, indent=2),
                    'source': 'database',
                    'metadata': {
                        'created_at': survey_record.get('created_at'),
                        'title': survey_record.get('title'),
                        'status': survey_record.get('status')
                    }
                })
        except Exception as e:
            logger.warning(f"从数据库获取任务结果失败: {task_id}, error: {str(e)}")
    
    # 备选方案：从文件获取结果
    output_file = task.get('output_file')
    if not output_file or not os.path.exists(output_file):
        return jsonify({
            'success': False,
            'error': '输出结果不存在（数据库和文件都无法找到）'
        }), 404
    
    try:
        with open(output_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        logger.info(f"从文件获取任务结果: {task_id}")
        return jsonify({
            'success': True,
            'content': content,
            'source': 'file',
            'output_file': output_file
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f"读取输出文件失败: {str(e)}"
        }), 500


@app.route('/api/database/stats', methods=['GET'])
def get_database_stats():
    """获取数据库统计信息"""
    if not DATABASE_AVAILABLE:
        return jsonify({
            'success': False,
            'error': '数据库不可用'
        }), 503
    
    try:
        stats = mongo_manager.get_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        logger.error(f"获取数据库统计信息失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/database/health', methods=['GET'])
def database_health_check():
    """数据库健康检查"""
    if not DATABASE_AVAILABLE:
        return jsonify({
            'success': False,
            'status': 'unavailable',
            'message': '数据库模块未加载'
        }), 503
    
    try:
        is_healthy = mongo_manager.health_check()
        if is_healthy:
            return jsonify({
                'success': True,
                'status': 'healthy',
                'message': '数据库连接正常'
            })
        else:
            return jsonify({
                'success': False,
                'status': 'unhealthy',
                'message': '数据库连接失败'
            }), 503
    except Exception as e:
        logger.error(f"数据库健康检查失败: {str(e)}")
        return jsonify({
            'success': False,
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/database/surveys', methods=['GET'])
def list_database_surveys():
    """获取数据库中的survey列表"""
    if not DATABASE_AVAILABLE:
        return jsonify({
            'success': False,
            'error': '数据库不可用'
        }), 503
    
    try:
        status = request.args.get('status')
        limit = int(request.args.get('limit', 100))
        skip = int(request.args.get('skip', 0))
        
        surveys = mongo_manager.list_surveys(status=status, limit=limit, skip=skip)
        
        return jsonify({
            'success': True,
            'surveys': surveys,
            'count': len(surveys)
        })
    except Exception as e:
        logger.error(f"获取数据库survey列表失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def cleanup_global_pipeline():
    """清理全局pipeline资源"""
    global global_pipeline, pipeline_monitor
    
    if global_pipeline is not None:
        logger.info("正在关闭全局pipeline...")
        try:
            global_pipeline.end()
            logger.info("全局pipeline已关闭")
        except Exception as e:
            logger.error(f"关闭全局pipeline时出错: {str(e)}")
        finally:
            global_pipeline = None
    
    if pipeline_monitor is not None:
        logger.info("清理pipeline监控器引用...")
        # 注意：Monitor类没有stop方法，且使用单例模式
        # 监控线程会在主程序退出时自动结束
        pipeline_monitor = None


if __name__ == '__main__':
    # 添加命令行参数解析
    import argparse
    parser = argparse.ArgumentParser(description='启动LLMxMapReduce Web演示服务')
    parser.add_argument('--language', type=str, default=None, help='提示语言，例如 "zh" 表示中文, "en" 表示英文')
    args = parser.parse_args()
    
    # 设置环境变量
    os.environ['PYTHONPATH'] = f"{os.getcwd()}:{os.environ.get('PYTHONPATH', '')}"
    
    # 根据命令行参数设置语言
    if args.language:
        os.environ['PROMPT_LANGUAGE'] = args.language
        logger.info(f"设置提示语言为: {args.language}")
    
    os.environ['OPENAI_API_KEY'] = "7891b3e1-51cf-4979-9eae-ecdf4e411d5e"
    os.environ['OPENAI_API_BASE'] = "https://ark.cn-beijing.volces.com/api/v3"
    os.environ['SERPER_API_KEY'] = "769aed5f5ca7b1ad747d71b57224eb53135d0069"

    
    # 记录启动信息
    logger.info("Web服务器启动中（使用全局pipeline模式）...")
    
    try:
        # 启动Flask应用
        app.run(host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭服务...")
    finally:
        # 清理资源
        cleanup_global_pipeline()
    
    logger.info("Web服务器已关闭") 