"""
路径验证和修正模块

负责验证和修正文件路径，防止路径注入、非法字符等安全风险
"""
import os
import re
import hashlib
import logging
from typing import Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class PathValidator:
    """路径验证和修正类
    
    提供文件路径的安全验证和自动修正功能，包括：
    - 非法字符过滤
    - 路径遍历防护
    - 文件名长度限制
    - 重复文件名处理
    """
    
    # 不同操作系统的非法字符
    ILLEGAL_CHARS = {
        'windows': r'[<>:"/\\|?*\x00-\x1f]',
        'unix': r'[/\x00]',
        'common': r'[<>:"/\\|?*\x00-\x1f]'  # 通用严格模式
    }
    
    # 保留文件名（Windows）
    RESERVED_NAMES = {
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    }
    
    def __init__(self, 
                 max_filename_length: int = 200,
                 max_path_length: int = 4000,
                 strict_mode: bool = True):
        """
        初始化路径验证器
        
        Args:
            max_filename_length: 最大文件名长度
            max_path_length: 最大路径长度
            strict_mode: 是否使用严格模式（使用通用非法字符集）
        """
        self.max_filename_length = max_filename_length
        self.max_path_length = max_path_length
        self.strict_mode = strict_mode
        
        # 选择字符过滤模式
        if strict_mode:
            self.illegal_pattern = re.compile(self.ILLEGAL_CHARS['common'])
        else:
            import platform
            system = platform.system().lower()
            if 'windows' in system:
                self.illegal_pattern = re.compile(self.ILLEGAL_CHARS['windows'])
            else:
                self.illegal_pattern = re.compile(self.ILLEGAL_CHARS['unix'])
    
    def sanitize_filename(self, filename: str, replacement: str = '_') -> str:
        """
        清理文件名，移除或替换非法字符
        
        Args:
            filename: 原始文件名
            replacement: 替换字符
            
        Returns:
            清理后的文件名
        """
        if not filename:
            return 'unnamed'
        
        # 移除前后空格
        filename = filename.strip()
        
        # 替换非法字符
        sanitized = self.illegal_pattern.sub(replacement, filename)
        
        # 移除连续的替换字符
        sanitized = re.sub(f'{re.escape(replacement)}+', replacement, sanitized)
        
        # 移除开头和结尾的替换字符
        sanitized = sanitized.strip(replacement)
        
        # 处理空结果
        if not sanitized:
            sanitized = 'unnamed'
        
        # 检查保留名称（只检查文件名部分，不包括扩展名）
        name_part = os.path.splitext(sanitized)[0].upper()
        if name_part in self.RESERVED_NAMES:
            name, ext = os.path.splitext(sanitized)
            sanitized = f"{name}_file{ext}"
        
        # 处理长度限制
        if len(sanitized) > self.max_filename_length:
            # 保留扩展名
            name, ext = os.path.splitext(sanitized)
            max_name_length = self.max_filename_length - len(ext) - 8  # 为hash预留空间
            
            if max_name_length > 0:
                # 截断并添加hash
                truncated = name[:max_name_length]
                name_hash = hashlib.md5(name.encode('utf-8')).hexdigest()[:8]
                sanitized = f"{truncated}_{name_hash}{ext}"
            else:
                # 文件名太长，使用hash
                name_hash = hashlib.md5(sanitized.encode('utf-8')).hexdigest()
                sanitized = f"file_{name_hash}{ext}"
        
        return sanitized
    
    def validate_path_traversal(self, path: str, allow_absolute: bool = False) -> bool:
        """
        检查路径是否包含路径遍历攻击
        
        Args:
            path: 要检查的路径
            allow_absolute: 是否允许绝对路径
            
        Returns:
            True表示安全，False表示存在风险
        """
        # 标准化路径
        normalized = os.path.normpath(path)
        
        # 检查是否包含父目录引用
        if '..' in normalized.split(os.sep):
            return False
        
        # 检查原始路径中是否包含 ../
        if '../' in path or '..\\' in path:
            return False
        
        # 检查是否为绝对路径（在某些情况下可能不安全）
        if not allow_absolute and os.path.isabs(normalized):
            return False
        
        return True
    
    def create_safe_path(self, 
                        base_dir: str,
                        filename: str,
                        ensure_unique: bool = True) -> Tuple[str, bool]:
        """
        创建安全的文件路径
        
        Args:
            base_dir: 基础目录
            filename: 文件名
            ensure_unique: 是否确保文件名唯一
            
        Returns:
            (安全路径, 是否被修改)
        """
        original_filename = filename
        modified = False
        
        # 清理文件名
        safe_filename = self.sanitize_filename(filename)
        if safe_filename != filename:
            modified = True
            logger.warning(f"文件名已修正: '{filename}' -> '{safe_filename}'")
        
        # 构建路径
        safe_path = os.path.join(base_dir, safe_filename)
        
        # 检查路径长度
        if len(safe_path) > self.max_path_length:
            # 缩短文件名
            name, ext = os.path.splitext(safe_filename)
            available_length = self.max_path_length - len(base_dir) - len(ext) - 10
            
            if available_length > 0:
                truncated_name = name[:available_length]
                name_hash = hashlib.md5(original_filename.encode('utf-8')).hexdigest()[:8]
                safe_filename = f"{truncated_name}_{name_hash}{ext}"
                safe_path = os.path.join(base_dir, safe_filename)
                modified = True
                logger.warning(f"路径过长已截断: {safe_path}")
        
        # 确保路径安全（允许绝对路径，因为我们在创建安全路径）
        if not self.validate_path_traversal(safe_path, allow_absolute=True):
            raise ValueError(f"不安全的路径: {safe_path}")
        
        # 确保唯一性
        if ensure_unique and os.path.exists(safe_path):
            safe_path = self._make_unique_path(safe_path)
            modified = True
        
        return safe_path, modified
    
    def _make_unique_path(self, path: str) -> str:
        """
        生成唯一的文件路径
        
        Args:
            path: 原始路径
            
        Returns:
            唯一的路径
        """
        base, ext = os.path.splitext(path)
        counter = 1
        
        while os.path.exists(path):
            path = f"{base}_{counter}{ext}"
            counter += 1
            
            # 防止无限循环
            if counter > 1000:
                import time
                timestamp = int(time.time() * 1000)
                path = f"{base}_{timestamp}{ext}"
                break
        
        return path
    
    def validate_output_path(self, 
                           topic: str,
                           timestamp: str,
                           suffix: str = 'result',
                           extension: str = 'jsonl',
                           base_dir: str = 'output') -> str:
        """
        验证和生成输出文件路径
        
        Args:
            topic: 主题名称
            timestamp: 时间戳
            suffix: 文件后缀
            extension: 文件扩展名
            base_dir: 基础目录
            
        Returns:
            安全的输出路径
        """
        # 清理主题名称
        safe_topic = self.sanitize_filename(topic)
        
        # 构建文件名
        filename = f"{safe_topic}_{timestamp}_{suffix}.{extension}"
        
        # 创建安全路径
        safe_path, modified = self.create_safe_path(base_dir, filename)
        
        if modified:
            logger.info(f"输出路径已修正: {safe_path}")
        
        # 确保目录存在
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        
        return safe_path
    
    def validate_input_path(self, input_path: str) -> bool:
        """
        验证输入文件路径的安全性
        
        Args:
            input_path: 输入文件路径
            
        Returns:
            True表示安全，False表示存在风险
        """
        try:
            # 检查路径遍历（允许绝对路径，因为输入文件可能是绝对路径）
            if not self.validate_path_traversal(input_path, allow_absolute=True):
                logger.error(f"输入路径包含路径遍历: {input_path}")
                return False
            
            # 检查文件是否存在
            if not os.path.exists(input_path):
                logger.error(f"输入文件不存在: {input_path}")
                return False
            
            # 检查是否为文件
            if not os.path.isfile(input_path):
                logger.error(f"输入路径不是文件: {input_path}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"验证输入路径时出错: {str(e)}")
            return False


# 全局实例
path_validator = PathValidator()


def get_path_validator() -> PathValidator:
    """获取全局路径验证器实例"""
    return path_validator 