import unittest
import logging
import sys
import os
import argparse
from typing import List, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def discover_tests(test_dir: str = "tests", pattern: str = "test_*.py") -> unittest.TestSuite:
    """发现测试案例
    
    Args:
        test_dir: 测试目录
        pattern: 测试文件匹配模式
        
    Returns:
        unittest.TestSuite: 测试套件
    """
    return unittest.defaultTestLoader.discover(test_dir, pattern=pattern)

def run_specific_tests(test_names: List[str]) -> unittest.TestResult:
    """运行指定的测试案例
    
    Args:
        test_names: 测试名称列表，格式为"模块.类.方法"
        
    Returns:
        unittest.TestResult: 测试结果
    """
    suite = unittest.TestSuite()
    
    for test_name in test_names:
        parts = test_name.split(".")
        
        if len(parts) == 1:
            # 只指定了模块名，运行整个模块
            module_name = f"tests.{parts[0]}"
            try:
                tests = unittest.defaultTestLoader.loadTestsFromName(module_name)
                suite.addTests(tests)
            except (ImportError, AttributeError) as e:
                logger.error(f"无法加载测试模块 {module_name}: {str(e)}")
        elif len(parts) == 2:
            # 指定了模块名和类名，运行整个类
            module_class = f"tests.{parts[0]}.{parts[1]}"
            try:
                tests = unittest.defaultTestLoader.loadTestsFromName(module_class)
                suite.addTests(tests)
            except (ImportError, AttributeError) as e:
                logger.error(f"无法加载测试类 {module_class}: {str(e)}")
        elif len(parts) == 3:
            # 指定了模块名、类名和方法名，运行单个方法
            module_class_method = f"tests.{parts[0]}.{parts[1]}.{parts[2]}"
            try:
                tests = unittest.defaultTestLoader.loadTestsFromName(module_class_method)
                suite.addTests(tests)
            except (ImportError, AttributeError) as e:
                logger.error(f"无法加载测试方法 {module_class_method}: {str(e)}")
        else:
            logger.error(f"无效的测试名称格式: {test_name}")
    
    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite)

def run_all_tests() -> unittest.TestResult:
    """运行所有测试案例
    
    Returns:
        unittest.TestResult: 测试结果
    """
    suite = discover_tests()
    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite)

def parse_args() -> argparse.Namespace:
    """解析命令行参数
    
    Returns:
        argparse.Namespace: 解析后的参数
    """
    parser = argparse.ArgumentParser(description="运行游戏测试案例")
    
    # 添加参数
    parser.add_argument(
        "-t", "--tests",
        nargs="*",
        help="要运行的测试名称列表，格式为'模块'、'模块.类'或'模块.类.方法'，例如'test_room_management'或'test_room_management.TestRoomManagement'或'test_room_management.TestRoomManagement.test_create_room'"
    )
    
    parser.add_argument(
        "-m", "--module",
        help="要运行的测试模块，例如'test_room_management'"
    )
    
    parser.add_argument(
        "-c", "--class",
        dest="class_name",
        help="要运行的测试类，例如'TestRoomManagement'"
    )
    
    parser.add_argument(
        "-f", "--function",
        help="要运行的测试方法，例如'test_create_room'"
    )
    
    return parser.parse_args()

def main():
    """主函数"""
    args = parse_args()
    
    # 确保当前目录是项目根目录
    if not os.path.exists("tests"):
        logger.error("当前目录不是项目根目录，请在项目根目录运行此脚本")
        return
    
    # 根据参数决定运行哪些测试
    if args.tests:
        # 运行指定的测试
        result = run_specific_tests(args.tests)
    elif args.module:
        # 运行指定模块的测试
        module_name = args.module
        if not module_name.startswith("test_"):
            module_name = f"test_{module_name}"
        
        if args.class_name:
            class_name = args.class_name
            if args.function:
                # 运行指定模块、类和方法的测试
                test_name = f"{module_name}.{class_name}.{args.function}"
            else:
                # 运行指定模块和类的测试
                test_name = f"{module_name}.{class_name}"
        else:
            # 运行指定模块的测试
            test_name = module_name
        
        result = run_specific_tests([test_name])
    else:
        # 运行所有测试
        result = run_all_tests()
    
    # 输出测试结果
    logger.info(f"测试完成: 运行 {result.testsRun} 个测试")
    logger.info(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    logger.info(f"失败: {len(result.failures)}")
    logger.info(f"错误: {len(result.errors)}")
    
    # 输出失败的测试
    if result.failures:
        logger.error("失败的测试:")
        for test, traceback in result.failures:
            logger.error(f"  {test}")
            logger.error(f"  {traceback}")
    
    # 输出错误的测试
    if result.errors:
        logger.error("错误的测试:")
        for test, traceback in result.errors:
            logger.error(f"  {test}")
            logger.error(f"  {traceback}")
    
    # 返回状态码
    return 0 if result.wasSuccessful() else 1

if __name__ == "__main__":
    sys.exit(main())
