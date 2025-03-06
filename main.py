#!/usr/bin/env python

import sys
import os
import asyncio
import argparse
import logging
import yaml
from typing import Dict, Any

from services.game_server import GameServer
from services.ai_service import OpenAIService
from adapters.dingtalk import DingTalkAdapter
from utils.logging import setup_logger

# 确保项目根目录在sys.path中
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

def load_config(config_path: str) -> Dict[str, Any]:
    """加载配置文件"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logging.warning(f"配置文件 {config_path} 未找到，将使用环境变量或默认值")
        return {}

async def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='TRPG游戏服务器')
    parser.add_argument('--config', default='config/ding_config.yaml', help='配置文件路径')
    parser.add_argument('--log-level', default='INFO', help='日志级别')
    parser.add_argument('--web', action='store_true', help='启动Web服务器')
    parser.add_argument('--web-port', type=int, default=8000, help='Web服务器端口')
    parser.add_argument('--web-host', default='0.0.0.0', help='Web服务器主机')
    parser.add_argument('--no-dingtalk', action='store_true', help='不启动钉钉适配器')
    args = parser.parse_args()
    
    # 设置日志
    logger = setup_logger(args.log_level)
    logger.info("启动TRPG游戏服务器")
    
    try:
        # 加载配置
        config = load_config(args.config)
        
        # 创建AI服务
        ai_service = OpenAIService()
        
        # 创建游戏服务器
        server = GameServer(ai_service)
        
        # 输出服务器信息
        logger.info("服务器配置信息:")
        logger.info(f"- 配置文件: {args.config}")
        logger.info(f"- 日志级别: {args.log_level}")
        logger.info(f"- Web服务器: {'启用' if args.web else '禁用'}")
        if args.web:
            logger.info(f"  - 主机: {args.web_host}")
            logger.info(f"  - 端口: {args.web_port}")
        logger.info(f"- 钉钉适配器: {'禁用' if args.no_dingtalk else '启用'}")
        logger.info("- 环境变量支持:")
        logger.info(f"  - OPENAI_API_KEY: {'已设置' if os.environ.get('OPENAI_API_KEY') else '未设置'}")
        logger.info(f"  - OPENAI_MODEL: {os.environ.get('OPENAI_MODEL', '未设置')}")
        logger.info(f"  - DINGTALK_CLIENT_ID: {'已设置' if os.environ.get('DINGTALK_CLIENT_ID') else '未设置'}")
        logger.info(f"  - DINGTALK_CLIENT_SECRET: {'已设置' if os.environ.get('DINGTALK_CLIENT_SECRET') else '未设置'}")
        
        # 创建并注册适配器
        web_adapter = None
        web_server_task = None
        
        # 如果启用钉钉适配器
        if not args.no_dingtalk:
            # 创建钉钉适配器
            dingtalk_adapter = DingTalkAdapter(
                config.get('client_id', ''),
                config.get('client_secret', '')
            )
            # 注册适配器
            server.register_adapter(dingtalk_adapter)
            logger.info("钉钉适配器已注册")
        
        # 如果启用Web服务器
        if args.web:
            # 导入Web服务器模块
            from web.server import init_web_adapter, start_server
            
            # 初始化Web适配器
            web_adapter = init_web_adapter(server)
            logger.info("Web适配器已注册")
            
            # 创建Web服务器任务
            web_server_task = asyncio.create_task(
                start_server(host=args.web_host, port=args.web_port)
            )
            logger.info(f"Web服务器任务已创建，将在 http://{args.web_host}:{args.web_port} 上运行")
        
        # 启动服务器
        await server.start()
        
        # 等待终止信号
        try:
            # 无限运行，直到收到键盘中断
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("收到终止信号，正在关闭服务器...")
        finally:
            # 停止服务器
            await server.stop()
            
            # 取消Web服务器任务
            if web_server_task:
                web_server_task.cancel()
                try:
                    await web_server_task
                except asyncio.CancelledError:
                    pass
            
    except Exception as e:
        logger.exception(f"服务器启动失败: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())
