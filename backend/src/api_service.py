"""
API服务模块

提供RESTful API接口，支持任务管理和状态查询
"""
import os
import json
import logging
from typing import Dict, Any, Optional
from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity

from src.task_manager import TaskStatus, get_task_manager
from src.pipeline_processor import PipelineTaskManager
from src.database.mongo_manager import get_mongo_manager
from src.common_service.helpers import jwt_required_custom

logger = logging.getLogger(__name__)

# 创建蓝图
api_bp = Blueprint('task', __name__)

# 全局变量
pipeline_task_manager: Optional[PipelineTaskManager] = None

def set_pipeline_manager(manager: PipelineTaskManager):
    """设置Pipeline任务管理器"""
    global pipeline_task_manager
    pipeline_task_manager = manager


@api_bp.route('/task/submit', methods=['POST'])
@jwt_required_custom
def submit_task():
    """提交新的任务
    
    请求体参数:
        topic: 研究主题
        description: 主题描述
        output_file: 输出文件路径（可选）
        config_file: 配置文件路径（可选）
        search_model: 搜索模型（可选）
        block_count: 块数量（可选）
        data_num: 数据数量（可选）
        top_n: 返回结果数量（可选）
        input_file: 输入文件路径（可选，与topic互斥）
    
    返回:
        task_id: 任务ID
        message: 状态消息
    """
    try:
        if not pipeline_task_manager:
            return jsonify({
                'success': False,
                'error': 'Pipeline管理器未初始化'
            }), 500
        
        # 获取当前用户ID
        current_user_id = get_jwt_identity()
        if not current_user_id:
            return jsonify({
                'success': False,
                'error': '无法获取用户信息'
            }), 401
        
        # 获取请求参数
        params = request.json
        if not params:
            return jsonify({
                'success': False,
                'error': '请求参数不能为空'
            }), 400
        
        # 添加用户ID到参数中
        params['user_id'] = current_user_id
        
        logger.info(f"收到Pipeline请求: {params}")
        
        # 提交任务
        task_id = pipeline_task_manager.submit_task(params)
        
        # 获取任务信息
        task_manager = get_task_manager()
        task = task_manager.get_task(task_id)
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': '任务已提交',
            'output_file': task['params'].get('output_file'),
            'original_topic': task.get('original_topic'),
            'unique_survey_title': task.get('expected_survey_title')
        })
        
    except Exception as e:
        logger.exception("启动Pipeline失败")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/task/<task_id>', methods=['GET'])
def get_task_status(task_id: str):
    """获取任务状态
    
    路径参数:
        task_id: 任务ID
    
    返回:
        task: 任务详细信息
    """
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


@api_bp.route('/task/<task_id>/pipeline_status', methods=['GET'])
def get_pipeline_status(task_id: str):
    """获取任务相关的Pipeline状态
    
    路径参数:
        task_id: 任务ID
    
    返回:
        pipeline状态信息
    """
    task_manager = get_task_manager()
    task = task_manager.get_task(task_id)
    
    if not task:
        return jsonify({
            'success': False,
            'error': '任务不存在'
        }), 404
    
    # 获取全局pipeline状态
    global_pipeline = pipeline_task_manager.global_pipeline if pipeline_task_manager else None
    
    response = {
        'success': True,
        'task_id': task_id,
        'status': task['status'],
        'pipeline_running': False,
        'nodes': [],
        'is_global_pipeline': True
    }
    
    if global_pipeline:
        response['pipeline_running'] = global_pipeline.is_start
        
        # 获取各节点状态
        for node_name, node in global_pipeline.all_nodes.items():
            node_info = {
                'name': node_name,
                'is_running': node.is_start,
                'status': '运行中' if node.is_start else '已停止'
            }
            
            if hasattr(node, 'src_queue'):
                node_info.update({
                    'queue_size': node.src_queue.qsize(),
                    'max_queue_size': node.src_queue.maxsize,
                    'executing_count': len(node.executing_data_queue) if hasattr(node, 'executing_data_queue') else 0,
                    'worker_count': getattr(node, 'worker_num', 0)
                })
            
            response['nodes'].append(node_info)
    
    return jsonify(response)


@api_bp.route('/global_pipeline_status', methods=['GET'])
def get_global_pipeline_status():
    """获取全局Pipeline状态"""
    task_manager = get_task_manager()
    global_pipeline = pipeline_task_manager.global_pipeline if pipeline_task_manager else None
    
    response = {
        'success': True,
        'pipeline_initialized': global_pipeline is not None,
        'pipeline_running': False,
        'nodes': [],
        'active_tasks_count': task_manager.get_active_task_count(),
        'total_tasks_count': len(task_manager.list_tasks())
    }
    
    if global_pipeline:
        response['pipeline_running'] = global_pipeline.is_start
        
        for node_name, node in global_pipeline.all_nodes.items():
            node_info = {
                'name': node_name,
                'is_running': node.is_start,
                'status': '运行中' if node.is_start else '已停止'
            }
            
            if hasattr(node, 'src_queue'):
                node_info.update({
                    'queue_size': node.src_queue.qsize(),
                    'max_queue_size': node.src_queue.maxsize,
                    'executing_count': len(node.executing_data_queue) if hasattr(node, 'executing_data_queue') else 0,
                    'worker_count': getattr(node, 'worker_num', 0)
                })
            
            response['nodes'].append(node_info)
    
    return jsonify(response)


@api_bp.route('/tasks', methods=['GET'])
def list_tasks():
    """获取任务列表
    
    查询参数:
        status: 状态过滤（可选）
        limit: 返回数量限制（默认100）
    
    返回:
        tasks: 任务列表
    """
    status = request.args.get('status')
    limit = int(request.args.get('limit', 100))
    
    task_manager = get_task_manager()
    
    # 转换状态字符串为枚举
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
        'count': len(tasks),
        'global_pipeline_mode': True
    })


@api_bp.route('/output/<task_id>', methods=['GET'])
def get_task_output(task_id: str):
    """获取任务输出结果
    
    路径参数:
        task_id: 任务ID
    
    返回:
        content: 输出内容
        source: 数据来源（database/file）
    """
    task_manager = get_task_manager()
    task = task_manager.get_task(task_id)
    
    if not task:
        return jsonify({
            'success': False,
            'error': '任务不存在'
        }), 404
    
    if task['status'] != TaskStatus.COMPLETED.value:
        return jsonify({
            'success': False,
            'error': f"任务尚未完成，当前状态：{task['status']}"
        }), 400
    
    # 优先从数据库获取
    try:
        from src.database.mongo_manager import get_mongo_manager
        mongo_manager = get_mongo_manager()
        if mongo_manager:
            survey = mongo_manager.get_survey(task_id)
            if survey and survey.get('survey_data'):
                logger.info(f"从数据库获取任务结果: {task_id}")
                return jsonify({
                    'success': True,
                    'content': json.dumps(survey['survey_data'], ensure_ascii=False, indent=2),
                    'source': 'database',
                    'metadata': {
                        'created_at': survey.get('created_at'),
                        'title': survey.get('title'),
                        'status': survey.get('status')
                    }
                })
    except Exception as e:
        logger.warning(f"从数据库获取任务结果失败: {task_id}, error: {str(e)}")
    
    # 备选：从文件获取
    output_file = task['params'].get('output_file')
    if output_file and os.path.exists(output_file):
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
    
    return jsonify({
        'success': False,
        'error': '输出结果不存在（数据库和文件都无法找到）'
    }), 404


@api_bp.route('/database/stats', methods=['GET'])
def get_database_stats():
    """获取数据库统计信息"""
    try:
        from src.database.mongo_manager import get_mongo_manager
        mongo_manager = get_mongo_manager()
        if not mongo_manager:
            return jsonify({
                'success': False,
                'error': '数据库不可用'
            }), 503
        
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


@api_bp.route('/database/health', methods=['GET'])
def database_health_check():
    """数据库健康检查"""
    try:
        from src.database.mongo_manager import get_mongo_manager
        mongo_manager = get_mongo_manager()
        if not mongo_manager:
            return jsonify({
                'success': False,
                'status': 'unavailable',
                'message': '数据库模块未加载'
            }), 503
        
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


@api_bp.route('/task/<task_id>', methods=['DELETE'])
def delete_task(task_id: str):
    """删除任务
    
    路径参数:
        task_id: 任务ID
    
    返回:
        成功/失败状态
    """
    task_manager = get_task_manager()
    
    if task_manager.delete_task(task_id):
        return jsonify({
            'success': True,
            'message': f'任务 {task_id} 已删除'
        })
    else:
        return jsonify({
            'success': False,
            'error': '删除任务失败'
        }), 400


@api_bp.route('/health', methods=['GET'])
def health_check():
    """服务健康检查"""
    task_manager = get_task_manager()
    redis_healthy = task_manager.health_check()
    
    mongo_healthy = False
    try:
        from src.database.mongo_manager import get_mongo_manager
        mongo_manager = get_mongo_manager()
        if mongo_manager:
            mongo_healthy = mongo_manager.health_check()
    except:
        pass
    
    all_healthy = redis_healthy
    
    return jsonify({
        'success': all_healthy,
        'services': {
            'redis': {
                'status': 'healthy' if redis_healthy else 'unhealthy',
                'required': True
            },
            'mongodb': {
                'status': 'healthy' if mongo_healthy else 'unavailable',
                'required': False
            }
        }
    }), 200 if all_healthy else 503 