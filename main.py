#!/usr/bin/env python

import sys
import os
import asyncio
import argparse
import logging
import yaml
from typing import Dict, Any

# 确保项目根目录在sys.path中
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

from services.game_server import GameServer
from services.ai_service import OpenAIService
from adapters.dingtalk import DingTalkAdapter
from utils.logging import setup_logger

def load_config(config_path: str) -> Dict[str, Any]:
    """加载配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

async def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='TRPG游戏服务器')
    parser.add_argument('--config', default='config/ding_config.yaml', help='配置文件路径')
    parser.add_argument('--log-level', default='INFO', help='日志级别')
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
        
        # 创建钉钉适配器
        dingtalk_adapter = DingTalkAdapter(
            config.get('client_id', ''),
            config.get('client_secret', '')
        )
        
        # 注册适配器
        server.register_adapter(dingtalk_adapter)
        
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
            
    except Exception as e:
        logger.exception(f"服务器启动失败: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())
