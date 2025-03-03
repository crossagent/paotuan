#!/usr/bin/env python

import sys
import os
import argparse
import logging
import yaml  # 添加yaml库以读取配置文件
from dingtalk_stream import DingTalkStreamClient, Credential, ChatbotMessage
from api.handlers.game_handler import GameMessageHandler
from game.turn_system.logic import GameMatchLogic

# 将项目根目录添加到sys.path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

def setup_logger():
    logger = logging.getLogger()
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter('%(asctime)s %(name)-8s %(levelname)-8s %(message)s [%(filename)s:%(lineno)d]'))
    logger.addHandler(handler)

    config = load_config()
    log_level = getattr(logging, config.get('log_level', 'INFO').upper(), logging.INFO)
    logger.setLevel(log_level)

    return logger

def load_config():
    with open('config/ding_config.yaml', 'r') as file:
        config = yaml.safe_load(file)
    return config

def define_options():
    config = load_config()
    options = argparse.Namespace(
        client_id=config.get('client_id'),
        client_secret=config.get('client_secret')
    )
    return options

def main():
    logger = setup_logger()
    options = define_options()

    # 创建游戏状态实例并初始化房间
    game_logic = GameMatchLogic()

    game_logic.create_room("测试房间")

    logger.info("游戏初始化完成，等待玩家指令以开始游戏。")

    credential = Credential(options.client_id, options.client_secret)
    client = DingTalkStreamClient(credential)
    client.register_callback_handler(
        ChatbotMessage.TOPIC, 
        GameMessageHandler(game_logic, logger)  # 传入游戏状态
    )

    # 初始化完成后等待玩家输入触发回合流程
    logger.info("等待玩家输入以开始游戏回合")

    client.start_forever()

if __name__ == '__main__':
    main()
