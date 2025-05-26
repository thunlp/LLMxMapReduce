"""
路径验证器测试模块

测试路径验证器的各种功能和安全特性
"""
import os
import tempfile
from src.path_validator import PathValidator

def test_filename_sanitization():
    """测试文件名清理功能"""
    print("=== 测试文件名清理功能 ===")
    
    validator = PathValidator()
    
    test_cases = [
        # (输入, 期望结果类型)
        ("normal_file.txt", "normal_file.txt"),
        ("file with spaces.txt", "file with spaces.txt"),  # 空格在严格模式下不被替换
        ("file<>:\"/\\|?*.txt", "file_.txt"),  # 连续非法字符被合并为一个下划线
        ("../../../etc/passwd", ".._.._.._etc_passwd"),  # 点号不是非法字符
        ("CON.txt", "CON_file.txt"),
        ("", "unnamed"),
        ("   ", "unnamed"),
        ("a" * 300 + ".txt", None),  # 长文件名，会被截断
    ]
    
    for original, expected in test_cases:
        result = validator.sanitize_filename(original)
        print(f"输入: '{original}' -> 输出: '{result}'")
        
        if expected and expected != result:
            print(f"  警告: 期望 '{expected}', 实际 '{result}'")
        
        # 验证结果不包含非法字符
        illegal_chars = '<>:"/\\|?*'
        if any(char in result for char in illegal_chars):
            print(f"  错误: 结果仍包含非法字符: '{result}'")


def test_path_traversal_detection():
    """测试路径遍历检测"""
    print("\n=== 测试路径遍历检测 ===")
    
    validator = PathValidator()
    
    test_cases = [
        ("normal/path/file.txt", True),
        ("../../../etc/passwd", False),
        ("./file.txt", True),
        ("../file.txt", False),
        ("/absolute/path", False),
        ("path/../file.txt", False),
        ("path/./file.txt", True),
    ]
    
    for path, expected in test_cases:
        result = validator.validate_path_traversal(path)
        status = "✓" if result == expected else "✗"
        print(f"{status} '{path}' -> {result} (期望: {expected})")


def test_output_path_generation():
    """测试输出路径生成"""
    print("\n=== 测试输出路径生成 ===")
    
    validator = PathValidator()
    
    test_cases = [
        ("normal topic", "20240101_120000"),
        ("topic with spaces", "20240101_120000"),
        ("topic/with/slashes", "20240101_120000"),
        ("topic<>:\"|?*", "20240101_120000"),
        ("很长的主题名称" * 50, "20240101_120000"),
    ]
    
    for topic, timestamp in test_cases:
        try:
            result = validator.validate_output_path(
                topic=topic,
                timestamp=timestamp,
                suffix='test',
                extension='jsonl',
                base_dir='test_output'
            )
            print(f"主题: '{topic}' -> 路径: '{result}'")
            
            # 验证路径安全性
            if not validator.validate_path_traversal(result):
                print(f"  错误: 生成的路径不安全: '{result}'")
                
        except Exception as e:
            print(f"主题: '{topic}' -> 错误: {str(e)}")


def test_unique_path_generation():
    """测试唯一路径生成"""
    print("\n=== 测试唯一路径生成 ===")
    
    validator = PathValidator()
    
    # 创建临时目录
    with tempfile.TemporaryDirectory() as temp_dir:
        base_filename = "test_file.txt"
        
        # 创建第一个文件
        first_path, modified = validator.create_safe_path(temp_dir, base_filename)
        with open(first_path, 'w') as f:
            f.write("test")
        print(f"第一个文件: {first_path}")
        
        # 创建第二个文件（应该有不同的名称）
        second_path, modified = validator.create_safe_path(temp_dir, base_filename)
        print(f"第二个文件: {second_path}")
        print(f"是否修改: {modified}")
        
        if first_path == second_path:
            print("错误: 两个文件路径相同")
        else:
            print("✓ 成功生成唯一路径")


def test_input_path_validation():
    """测试输入路径验证"""
    print("\n=== 测试输入路径验证 ===")
    
    validator = PathValidator()
    
    # 创建临时文件用于测试
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
        temp_file.write("test content")
        temp_file_path = temp_file.name
    
    try:
        test_cases = [
            (temp_file_path, True),  # 存在的文件（绝对路径）
            ("nonexistent_file.txt", False),  # 不存在的文件
            ("../../../etc/passwd", False),  # 路径遍历
            ("/nonexistent/path/file.txt", False),  # 绝对路径但文件不存在
        ]
        
        for path, expected in test_cases:
            result = validator.validate_input_path(path)
            status = "✓" if result == expected else "✗"
            print(f"{status} '{path}' -> {result} (期望: {expected})")
            
    finally:
        # 清理临时文件
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


def test_edge_cases():
    """测试边界情况"""
    print("\n=== 测试边界情况 ===")
    
    validator = PathValidator()
    
    # 测试空输入
    try:
        result = validator.sanitize_filename("")
        print(f"空字符串 -> '{result}'")
    except Exception as e:
        print(f"空字符串处理错误: {e}")
    
    # 测试None输入
    try:
        result = validator.sanitize_filename(None)
        print(f"None -> '{result}'")
    except Exception as e:
        print(f"None处理错误: {e}")
    
    # 测试极长文件名
    long_name = "a" * 1000 + ".txt"
    try:
        result = validator.sanitize_filename(long_name)
        print(f"极长文件名 (长度: {len(long_name)}) -> '{result}' (长度: {len(result)})")
    except Exception as e:
        print(f"极长文件名处理错误: {e}")


def test_real_world_scenarios():
    """测试真实世界场景"""
    print("\n=== 测试真实世界场景 ===")
    
    validator = PathValidator()
    
    # 模拟真实的主题名称
    real_topics = [
        "机器学习与深度学习",
        "COVID-19 pandemic research",
        "Climate change & environmental impact",
        "AI/ML in healthcare: opportunities & challenges",
        "Blockchain technology: past, present & future",
        "量子计算的发展前景与挑战",
    ]
    
    timestamp = "20240101_120000"
    
    for topic in real_topics:
        try:
            output_path = validator.validate_output_path(
                topic=topic,
                timestamp=timestamp,
                suffix='survey',
                extension='jsonl',
                base_dir='output'
            )
            print(f"✓ '{topic}' -> '{output_path}'")
            
        except Exception as e:
            print(f"✗ '{topic}' -> 错误: {e}")


if __name__ == "__main__":
    print("开始测试路径验证器...")
    
    test_filename_sanitization()
    test_path_traversal_detection()
    test_output_path_generation()
    test_unique_path_generation()
    test_input_path_validation()
    test_edge_cases()
    test_real_world_scenarios()
    
    print("\n测试完成！") 