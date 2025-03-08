import unittest
import logging
import sys
from typing import Dict, List, Any, Optional

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
    
    def test_start_game(self):
        """测试开始游戏"""
        # 创建测试房间，所有玩家已准备
        room_result = self.helpers.create_test_room("测试房间", 3, True)
        self.assertIsNotNone(room_result, "创建测试房间失败")
        room_id = room_result.get("id")
        
        # 设置剧本
        scenario_id = "asylum"
        scenario_result = self.api_client.set_scenario(room_id, scenario_id)
        self.assertIsNotNone(scenario_result, "设置剧本失败")
        self.assertTrue(scenario_result.get("success"), "设置剧本操作未成功")
        
        # 开始游戏
        start_result = self.api_client.start_game(room_id, "测试场景", scenario_id)
        self.assertIsNotNone(start_result, "开始游戏失败")
        
        # 验证游戏状态
        room = self.api_client.get_room(room_id)
        self.assertIsNotNone(room.get("current_match"), "未找到当前游戏局")
        self.assertEqual(room.get("current_match").get("status"), "RUNNING", "游戏状态不正确")
        self.assertEqual(room.get("current_match").get("scenario_id"), scenario_id, "剧本ID不匹配")
    
    def test_character_selection(self):
        """测试角色选择"""
        # 创建测试房间和游戏
        room_result = self.helpers.create_test_room("测试房间", 3, True)
        self.assertIsNotNone(room_result, "创建测试房间失败")
        room_id = room_result.get("id")
        
        game_result = self.helpers.create_test_game(room_id)
        self.assertIsNotNone(game_result, "创建测试游戏失败")
        
        # 选择角色
        character_name = "测试角色"
        select_result = self.api_client.select_character(room_id, character_name)
        self.assertIsNotNone(select_result, "选择角色失败")
        self.assertTrue(select_result.get("success"), "选择角色操作未成功")
        
        # 验证角色选择结果
        room = self.api_client.get_room(room_id)
        current_player = None
        for player in room.get("players"):
            if player.get("id") == "test_user":  # 假设当前用户ID为test_user
                current_player = player
                break
        
        self.assertIsNotNone(current_player, "未找到当前玩家")
        self.assertIsNotNone(current_player.get("character_id"), "未找到角色ID")
    
    def test_dm_turn(self):
        """测试DM回合"""
        # 创建完整游戏环境
        room_id, match_id, player_ids = self.helpers.setup_complete_game()
        self.assertIsNotNone(room_id, "创建游戏环境失败")
        
        # 创建DM回合
        narration = "这是一个测试DM回合，描述了当前场景和情况。"
        turn_result = self.helpers.create_test_dm_turn(room_id, narration)
        self.assertIsNotNone(turn_result, "创建DM回合失败")
        
        # 验证回合状态
        game_state = self.api_client.get_debug_game_state()
        self.assertIsNotNone(game_state, "获取游戏状态失败")
        
        # 查找当前回合
        current_turn = None
        for room_info in game_state.get("rooms", []):
            if room_info.get("id") == room_id:
                for match in room_info.get("matches", []):
                    if match.get("id") == match_id:
                        for turn in match.get("turns", []):
                            if turn.get("id") == turn_result.get("turn_id"):
                                current_turn = turn
                                break
        
        self.assertIsNotNone(current_turn, "未找到当前回合")
        self.assertEqual(current_turn.get("turn_type"), "DM", "回合类型不正确")
        self.assertEqual(current_turn.get("narration"), narration, "DM叙述内容不匹配")
    
    def test_player_action_turn(self):
        """测试玩家行动回合"""
        # 创建完整游戏环境
        room_id, match_id, player_ids = self.helpers.setup_complete_game()
        self.assertIsNotNone(room_id, "创建游戏环境失败")
        
        # 创建玩家行动回合
        turn_result = self.helpers.create_test_player_turn(room_id, player_ids)
        self.assertIsNotNone(turn_result, "创建玩家行动回合失败")
        
        # 模拟玩家行动
        for player_id in player_ids:
            action_result = self.helpers.simulate_player_action(
                room_id=room_id,
                player_id=player_id,
                action=f"玩家{player_id}的行动"
            )
            self.assertIsNotNone(action_result, f"模拟玩家{player_id}行动失败")
            self.assertTrue(action_result.get("success"), f"玩家{player_id}行动操作未成功")
        
        # 验证所有玩家都已行动
        game_state = self.api_client.get_debug_game_state()
        self.assertIsNotNone(game_state, "获取游戏状态失败")
        
        # 查找当前回合
        current_turn = None
        for room_info in game_state.get("rooms", []):
            if room_info.get("id") == room_id:
                for match in room_info.get("matches", []):
                    if match.get("id") == match_id:
                        for turn in match.get("turns", []):
                            if turn.get("id") == turn_result.get("turn_id"):
                                current_turn = turn
                                break
        
        self.assertIsNotNone(current_turn, "未找到当前回合")
        self.assertEqual(current_turn.get("turn_type"), "PLAYER", "回合类型不正确")
        self.assertEqual(current_turn.get("status"), "COMPLETED", "回合状态不正确")
        
        # 验证所有玩家的行动都已记录
        actions = current_turn.get("actions", {})
        for player_id in player_ids:
            self.assertIn(player_id, actions, f"未找到玩家{player_id}的行动记录")
    
    def test_dice_turn(self):
        """测试骰子检定回合"""
        # 创建完整游戏环境
        room_id, match_id, player_ids = self.helpers.setup_complete_game()
        self.assertIsNotNone(room_id, "创建游戏环境失败")
        
        # 创建骰子检定回合
        difficulty = 10
        action_desc = "攀爬检定"
        turn_result = self.helpers.create_test_player_turn(
            room_id=room_id,
            active_players=player_ids,
            is_dice_turn=True,
            difficulty=difficulty,
            action_desc=action_desc
        )
        self.assertIsNotNone(turn_result, "创建骰子检定回合失败")
        
        # 模拟玩家骰子检定
        for player_id in player_ids:
            # 一半成功，一半失败
            roll = 15 if player_ids.index(player_id) % 2 == 0 else 5
            action_result = self.helpers.simulate_player_action(
                room_id=room_id,
                player_id=player_id,
                action=f"玩家{player_id}尝试攀爬",
                roll=roll
            )
            self.assertIsNotNone(action_result, f"模拟玩家{player_id}骰子检定失败")
            self.assertTrue(action_result.get("success"), f"玩家{player_id}骰子检定操作未成功")
            
            # 验证骰子结果
            result = action_result.get("result", {})
            self.assertEqual(result.get("roll"), roll, "骰子点数不匹配")
            self.assertEqual(result.get("difficulty"), difficulty, "难度不匹配")
            self.assertEqual(result.get("success"), roll >= difficulty, "成功判定不正确")
        
        # 验证所有玩家都已完成骰子检定
        game_state = self.api_client.get_debug_game_state()
        self.assertIsNotNone(game_state, "获取游戏状态失败")
        
        # 查找当前回合
        current_turn = None
        for room_info in game_state.get("rooms", []):
            if room_info.get("id") == room_id:
                for match in room_info.get("matches", []):
                    if match.get("id") == match_id:
                        for turn in match.get("turns", []):
                            if turn.get("id") == turn_result.get("turn_id"):
                                current_turn = turn
                                break
        
        self.assertIsNotNone(current_turn, "未找到当前回合")
        self.assertEqual(current_turn.get("turn_type"), "PLAYER", "回合类型不正确")
        self.assertEqual(current_turn.get("status"), "COMPLETED", "回合状态不正确")
        
        # 验证所有玩家的骰子结果都已记录
        dice_results = current_turn.get("dice_results", {})
        for player_id in player_ids:
            self.assertIn(player_id, dice_results, f"未找到玩家{player_id}的骰子结果")
    
    def test_complete_game_cycle(self):
        """测试完整游戏循环"""
        # 创建完整游戏环境
        room_id, match_id, player_ids = self.helpers.setup_complete_game()
        self.assertIsNotNone(room_id, "创建游戏环境失败")
        
        # 运行完整游戏循环
        success = self.helpers.run_complete_game_cycle(room_id, player_ids)
        self.assertTrue(success, "运行完整游戏循环失败")
        
        # 验证游戏状态
        game_state = self.api_client.get_debug_game_state()
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
            if m.get("id") == match_id:
                match_info = m
                break
        
        self.assertIsNotNone(match_info, "未找到游戏信息")
        
        # 验证回合数量
        self.assertGreaterEqual(len(match_info.get("turns", [])), 4, "回合数量不足")
        
        # 验证最后一个回合是DM回合
        last_turn = match_info.get("turns", [])[-1]
        self.assertEqual(last_turn.get("turn_type"), "DM", "最后一个回合不是DM回合")

if __name__ == "__main__":
    unittest.main()
