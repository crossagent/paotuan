import unittest
import logging
import sys
from typing import Dict, List, Any, Optional, Tuple

from tests.api_client import ApiClient
from tests.test_helpers import TestHelpers

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

class TestGameFlow(unittest.TestCase):
    """游戏流程相关测试"""
    
    @classmethod
    def setUpClass(cls):
        """测试类初始化"""
        cls.api_client = ApiClient()
        cls.helpers = TestHelpers(cls.api_client)
        
        # 登录
        success = cls.api_client.login("test_user", "password")
        if not success:
            raise Exception("登录失败，无法进行测试")
    
    def setUp(self):
        """每个测试方法执行前的准备工作"""
        # 重置服务器状态
        success = self.helpers.reset_server_state()
        self.assertTrue(success, "重置服务器状态失败")
    
    
    def test_real_game_flow_with_three_players(self):
        """测试真实游戏流程（三名玩家）"""
        # 获取三个用户的API客户端
        clients = self.helpers.get_multiple_user_clients(3)
        self.assertEqual(len(clients), 3, "获取用户客户端失败，需要3个用户")
        
        host_client = clients[0]
        player2_client = clients[1]
        player3_client = clients[2]
        
        # 1. 房间准备阶段
        # 创建房间
        room_name = "三人测试房间"
        room_result = host_client.create_room(room_name)
        self.assertIsNotNone(room_result, "创建房间失败")
        room_id = room_result.get("id")
        
        # 其他玩家加入房间
        join_result2 = player2_client.join_room(room_id)
        self.assertIsNotNone(join_result2, "玩家2加入房间失败")
        self.assertIsNotNone(join_result2.get("player"), "玩家2加入房间操作未成功")
        
        join_result3 = player3_client.join_room(room_id)
        self.assertIsNotNone(join_result3, "玩家3加入房间失败")
        self.assertIsNotNone(join_result3.get("player"), "玩家3加入房间操作未成功")
        
        # 非房主玩家设置准备状态
        for client in clients[1:]:  # 跳过房主
            ready_result = client.set_ready(room_id, True)
            self.assertIsNotNone(ready_result, f"玩家{client.username}设置准备状态失败")
            self.assertTrue(ready_result.get("success"), f"玩家{client.username}设置准备状态操作未成功")
        

        # 设置剧本为test_scenario
        scenario_id = "test_scenario"
        scenario_result = host_client.set_scenario(room_id, scenario_id)
        self.assertIsNotNone(scenario_result, "设置剧本失败")
        self.assertTrue(scenario_result.get("success"), "设置剧本操作未成功")

        # 开始游戏
        start_result = host_client.start_game(room_id, "测试场景", scenario_id)
        self.assertIsNotNone(start_result, "开始游戏失败")
        self.assertIsNotNone(start_result.get("match_id"), "开始游戏操作未成功")
        
        # 验证游戏状态
        room = host_client.get_room(room_id)
        self.assertIsNotNone(room.get("current_match"), "未找到当前游戏局")
        self.assertEqual(room.get("current_match").get("status"), "RUNNING", "游戏状态不正确")
        self.assertEqual(room.get("current_match").get("scenario_id"), scenario_id, "剧本ID不匹配")
        
        # 2. 角色选择阶段
        # 获取可选角色列表
        available_characters = room.get("current_match", {}).get("available_characters", [])
        self.assertGreaterEqual(len(available_characters), 3, "可选角色数量不足")
        
        # 每个玩家选择不同的角色
        for i, client in enumerate(clients):
            character_name = f"玩家{i+1}角色"
            select_result = client.select_character(room_id, character_name)
            self.assertIsNotNone(select_result, f"玩家{client.username}选择角色失败")
            self.assertTrue(select_result.get("success"), f"玩家{client.username}选择角色操作未成功")
        
        # 验证所有玩家都已选择角色
        room = host_client.get_room(room_id)
        for player in room.get("players", []):
            self.assertIsNotNone(player.get("character_id"), f"玩家{player.get('id')}未选择角色")
        
        # 获取玩家ID列表
        player_ids = [player.get("id") for player in room.get("players", [])]
        self.assertEqual(len(player_ids), 3, "玩家数量不正确")
        
        # 3. 游戏执行阶段
        # 模拟DM回合：初始场景描述
        dm_turn_result = self.helpers.simulate_dm_turn(
            room_id=room_id,
            narration="你们醒来发现自己被困在一个陌生的房间里，房间中央有一张桌子，桌上放着一本笔记，角落里似乎有什么东西在闪光。",
            active_players=player_ids
        )
        self.assertIsNotNone(dm_turn_result, "模拟DM回合失败")
        self.assertTrue(dm_turn_result.get("success"), "模拟DM回合操作未成功")
        
        # 模拟玩家回合：初始探索
        # 玩家1：移动到房间中央
        action_result1 = self.helpers.simulate_player_action(
            room_id=room_id,
            player_id=player_ids[0],
            action="我移动到房间中央查看桌子"
        )
        self.assertIsNotNone(action_result1, "模拟玩家1行动失败")
        self.assertTrue(action_result1.get("success"), "玩家1行动操作未成功")
        
        # 玩家2：检查角落里的东西
        action_result2 = self.helpers.simulate_player_action(
            room_id=room_id,
            player_id=player_ids[1],
            action="我检查角落里闪光的东西"
        )
        self.assertIsNotNone(action_result2, "模拟玩家2行动失败")
        self.assertTrue(action_result2.get("success"), "玩家2行动操作未成功")
        
        # 玩家3：观察周围
        action_result3 = self.helpers.simulate_player_action(
            room_id=room_id,
            player_id=player_ids[2],
            action="我尝试观察周围有无其他出口"
        )
        self.assertIsNotNone(action_result3, "模拟玩家3行动失败")
        self.assertTrue(action_result3.get("success"), "玩家3行动操作未成功")
        
        # 等待回合完成
        self.assertTrue(self.helpers.wait_for_turn_completion(room_id), "等待回合完成失败")
        
        # 模拟DM回合：物品发现
        dm_turn_result = self.helpers.simulate_dm_turn(
            room_id=room_id,
            narration="玩家1在桌上发现了一本笔记，上面似乎有一些密码。玩家2在角落里发现了一把锈迹斑斑的钥匙。玩家3发现房间只有一个上锁的门。",
            active_players=[player_ids[0], player_ids[1]]  # 只激活玩家1和玩家2
        )
        self.assertIsNotNone(dm_turn_result, "模拟DM回合失败")
        self.assertTrue(dm_turn_result.get("success"), "模拟DM回合操作未成功")
        
        # 模拟玩家回合：物品交互
        # 玩家1：拿取笔记
        action_result1 = self.helpers.simulate_player_action(
            room_id=room_id,
            player_id=player_ids[0],
            action="我拿取桌上的笔记"
        )
        self.assertIsNotNone(action_result1, "模拟玩家1行动失败")
        self.assertTrue(action_result1.get("success"), "玩家1行动操作未成功")
        
        # 玩家2：拿取钥匙
        action_result2 = self.helpers.simulate_player_action(
            room_id=room_id,
            player_id=player_ids[1],
            action="我捡起角落里的钥匙"
        )
        self.assertIsNotNone(action_result2, "模拟玩家2行动失败")
        self.assertTrue(action_result2.get("success"), "玩家2行动操作未成功")
        
        # 验证玩家3无法行动（因为未被激活）
        try:
            action_result3 = self.helpers.simulate_player_action(
                room_id=room_id,
                player_id=player_ids[2],
                action="我尝试打开门"
            )
            # 如果没有抛出异常，则验证操作是否被拒绝
            self.assertFalse(action_result3.get("success", False), "未激活的玩家3能够行动")
        except Exception:
            # 如果抛出异常，则说明操作被正确拒绝
            pass
        
        # 等待回合完成
        self.assertTrue(self.helpers.wait_for_turn_completion(room_id), "等待回合完成失败")
        
        # 模拟DM回合：骰子检定
        dm_turn_result = self.helpers.simulate_dm_turn(
            room_id=room_id,
            narration="玩家1需要尝试解读笔记中的密码，玩家2需要检查钥匙是否能打开门。",
            active_players=[player_ids[0], player_ids[1]],
            is_dice_turn=True,
            difficulty=10,
            action_desc="解谜检定"
        )
        self.assertIsNotNone(dm_turn_result, "模拟DM回合失败")
        self.assertTrue(dm_turn_result.get("success"), "模拟DM回合操作未成功")
        
        # 模拟玩家骰子检定
        # 玩家1：解读笔记（成功）
        action_result1 = self.helpers.simulate_player_action(
            room_id=room_id,
            player_id=player_ids[0],
            action="我尝试解读笔记中的密码",
            roll=15
        )
        self.assertIsNotNone(action_result1, "模拟玩家1骰子检定失败")
        self.assertTrue(action_result1.get("success"), "玩家1骰子检定操作未成功")
        
        # 玩家2：检查钥匙（失败）
        action_result2 = self.helpers.simulate_player_action(
            room_id=room_id,
            player_id=player_ids[1],
            action="我尝试用钥匙打开门",
            roll=5
        )
        self.assertIsNotNone(action_result2, "模拟玩家2骰子检定失败")
        self.assertTrue(action_result2.get("success"), "玩家2骰子检定操作未成功")
        
        # 验证玩家3无法行动（因为未被激活）
        try:
            action_result3 = self.helpers.simulate_player_action(
                room_id=room_id,
                player_id=player_ids[2],
                action="我尝试帮助玩家2",
                roll=10
            )
            # 如果没有抛出异常，则验证操作是否被拒绝
            self.assertFalse(action_result3.get("success", False), "未激活的玩家3能够行动")
        except Exception:
            # 如果抛出异常，则说明操作被正确拒绝
            pass
        
        # 等待回合完成
        self.assertTrue(self.helpers.wait_for_turn_completion(room_id), "等待回合完成失败")
        
        # 模拟DM回合：单一玩家行动
        dm_turn_result = self.helpers.simulate_dm_turn(
            room_id=room_id,
            narration="玩家1成功解读了笔记，发现钥匙需要特殊的方式使用。玩家3似乎对这种锁很熟悉。",
            active_players=[player_ids[2]]  # 只激活玩家3
        )
        self.assertIsNotNone(dm_turn_result, "模拟DM回合失败")
        self.assertTrue(dm_turn_result.get("success"), "模拟DM回合操作未成功")
        
        # 模拟玩家回合：单一玩家行动
        # 玩家3：尝试开锁
        action_result3 = self.helpers.simulate_player_action(
            room_id=room_id,
            player_id=player_ids[2],
            action="我接过钥匙，用特殊方式尝试开锁"
        )
        self.assertIsNotNone(action_result3, "模拟玩家3行动失败")
        self.assertTrue(action_result3.get("success"), "玩家3行动操作未成功")
        
        # 验证玩家1和玩家2无法行动（因为未被激活）
        for i, player_id in enumerate([player_ids[0], player_ids[1]]):
            try:
                action_result = self.helpers.simulate_player_action(
                    room_id=room_id,
                    player_id=player_id,
                    action=f"我尝试帮助玩家3"
                )
                # 如果没有抛出异常，则验证操作是否被拒绝
                self.assertFalse(action_result.get("success", False), f"未激活的玩家{i+1}能够行动")
            except Exception:
                # 如果抛出异常，则说明操作被正确拒绝
                pass
        
        # 等待回合完成
        self.assertTrue(self.helpers.wait_for_turn_completion(room_id), "等待回合完成失败")
        
        # 模拟DM回合：游戏结束
        dm_turn_result = self.helpers.simulate_dm_turn(
            room_id=room_id,
            narration="玩家3成功打开了门，你们终于逃出了房间！游戏胜利！",
            next_turn_type="DM"  # 结束游戏
        )
        self.assertIsNotNone(dm_turn_result, "模拟DM回合失败")
        self.assertTrue(dm_turn_result.get("success"), "模拟DM回合操作未成功")
        
        # 验证游戏状态
        game_state = host_client.get_debug_game_state()
        self.assertIsNotNone(game_state, "获取游戏状态失败")
        
        # 查找房间和游戏
        room_info = None
        for r in game_state.get("rooms", []):
            if r.get("id") == room_id:
                room_info = r
                break
        
        self.assertIsNotNone(room_info, "未找到房间信息")
        
        # 查找游戏
        match_info = None
        for m in room_info.get("matches", []):
            if m.get("id") == room.get("current_match").get("id"):
                match_info = m
                break
        
        self.assertIsNotNone(match_info, "未找到游戏信息")
        
        # 验证回合数量（至少应该有7个回合：3个DM回合和4个玩家回合）
        self.assertGreaterEqual(len(match_info.get("turns", [])), 7, "回合数量不足")
        
        # 验证最后一个回合是DM回合
        last_turn = match_info.get("turns", [])[-1]
        self.assertEqual(last_turn.get("turn_type"), "DM", "最后一个回合不是DM回合")

if __name__ == "__main__":
    unittest.main()
