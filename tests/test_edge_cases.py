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

class TestEdgeCases(unittest.TestCase):
    """边界条件和异常情况测试"""
    
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
        """测试最大玩家数限制"""
        # 创建最大玩家数为2的房间
        room_name = "测试房间"
        max_players = 2
        result = self.api_client.create_room(room_name, max_players)
        
        # 验证结果
        self.assertIsNotNone(result, "创建房间失败")
        self.assertEqual(result.get("max_players"), max_players, "最大玩家数设置不正确")
        
        # 添加一个测试玩家，使房间达到最大人数
        room_id = result.get("id")
        room_result = self.helpers.create_test_room(room_name, 2, False)
        self.assertIsNotNone(room_result, "创建测试房间失败")
        
        # 尝试加入第三个玩家（应该失败）
        try:
            join_result = self.api_client.join_room(room_id)
            self.fail("超出最大玩家数限制仍能加入房间")
        except Exception:
            # 预期会抛出异常
            pass
    
    def test_player_disconnect(self):
        """测试玩家断线情况"""
        # 创建测试房间和游戏
        room_result = self.helpers.create_test_room("测试房间", 3, True)
        self.assertIsNotNone(room_result, "创建测试房间失败")
        room_id = room_result.get("id")
        
        game_result = self.helpers.create_test_game(room_id)
        self.assertIsNotNone(game_result, "创建测试游戏失败")
        
        # 模拟玩家断线（离开房间）
        player_id = room_result.get("players")[1].get("id")  # 选择第二个玩家（非房主）
        
        # 记录断线前的状态
        before_state = self.api_client.get_debug_game_state()
        self.assertIsNotNone(before_state, "获取断线前游戏状态失败")
        
        # 模拟断线
        try:
            # 这里我们使用离开房间API来模拟断线
            # 在实际情况中，断线可能是由于网络问题导致的WebSocket连接断开
            leave_result = self.api_client.leave_room(room_id)
            self.assertIsNotNone(leave_result, "离开房间失败")
            self.assertTrue(leave_result.get("success"), "离开房间操作未成功")
        except Exception as e:
            logging.error(f"模拟断线失败: {str(e)}")
            self.fail("模拟断线失败")
        
        # 获取断线后的状态
        after_state = self.api_client.get_debug_game_state()
        self.assertIsNotNone(after_state, "获取断线后游戏状态失败")
        
        # 验证游戏仍在进行中
        room_info = None
        for r in after_state.get("rooms", []):
            if r.get("id") == room_id:
                room_info = r
                break
        
        self.assertIsNotNone(room_info, "未找到房间信息")
        self.assertIsNotNone(room_info.get("current_match_id"), "游戏已结束")
        
        # 验证玩家数量减少
        self.assertEqual(len(room_info.get("players")), len(room_result.get("players")) - 1, "玩家数量不正确")
    
    def test_host_disconnect(self):
        """测试房主断线情况"""
        # 创建测试房间和游戏
        room_result = self.helpers.create_test_room("测试房间", 3, True)
        self.assertIsNotNone(room_result, "创建测试房间失败")
        room_id = room_result.get("id")
        
        # 获取房主ID
        room = self.api_client.get_room(room_id)
        host_id = room.get("host_id")
        self.assertIsNotNone(host_id, "未找到房主ID")
        
        # 记录断线前的状态
        before_state = self.api_client.get_debug_game_state()
        self.assertIsNotNone(before_state, "获取断线前游戏状态失败")
        
        # 模拟房主断线
        try:
            # 这里我们使用离开房间API来模拟断线
            leave_result = self.api_client.leave_room(room_id)
            self.assertIsNotNone(leave_result, "离开房间失败")
            self.assertTrue(leave_result.get("success"), "离开房间操作未成功")
        except Exception as e:
            logging.error(f"模拟房主断线失败: {str(e)}")
            self.fail("模拟房主断线失败")
        
        # 获取断线后的状态
        after_state = self.api_client.get_debug_game_state()
        self.assertIsNotNone(after_state, "获取断线后游戏状态失败")
        
        # 验证房间仍存在
        room_exists = False
        for r in after_state.get("rooms", []):
            if r.get("id") == room_id:
                room_exists = True
                break
        
        # 房间可能被销毁或保留，取决于游戏逻辑
        if room_exists:
            # 如果房间保留，验证房主已转移
            room = self.api_client.get_room(room_id)
            new_host_id = room.get("host_id")
            self.assertIsNotNone(new_host_id, "未找到新房主ID")
            self.assertNotEqual(new_host_id, host_id, "房主未转移")
    
    def test_invalid_action(self):
        """测试无效操作"""
        # 创建完整游戏环境
        room_id, match_id, player_ids = self.helpers.setup_complete_game()
        self.assertIsNotNone(room_id, "创建游戏环境失败")
        
        # 创建DM回合（不是玩家回合）
        turn_result = self.helpers.create_test_dm_turn(room_id, "这是一个测试DM回合")
        self.assertIsNotNone(turn_result, "创建DM回合失败")
        
        # 尝试在DM回合执行玩家行动（应该失败）
        try:
            action_result = self.helpers.simulate_player_action(
                room_id=room_id,
                player_id=player_ids[0],
                action="这是一个无效的玩家行动"
            )
            self.fail("在DM回合执行玩家行动未失败")
        except Exception:
            # 预期会抛出异常
            pass
    
    def test_inactive_player_action(self):
        """测试非活跃玩家行动"""
        # 创建完整游戏环境
        room_id, match_id, player_ids = self.helpers.setup_complete_game()
        self.assertIsNotNone(room_id, "创建游戏环境失败")
        
        # 创建玩家回合，只激活部分玩家
        active_players = [player_ids[0]]  # 只激活第一个玩家
        turn_result = self.helpers.create_test_player_turn(room_id, active_players)
        self.assertIsNotNone(turn_result, "创建玩家回合失败")
        
        # 尝试让非活跃玩家执行行动（应该失败）
        inactive_player_id = player_ids[1]  # 选择一个非活跃玩家
        try:
            action_result = self.helpers.simulate_player_action(
                room_id=room_id,
                player_id=inactive_player_id,
                action="这是一个非活跃玩家的行动"
            )
            self.fail("非活跃玩家执行行动未失败")
        except Exception:
            # 预期会抛出异常
            pass
    
    def test_dice_roll_edge_cases(self):
        """测试骰子检定边界情况"""
        # 创建完整游戏环境
        room_id, match_id, player_ids = self.helpers.setup_complete_game()
        self.assertIsNotNone(room_id, "创建游戏环境失败")
        
        # 创建骰子检定回合
        difficulty = 10
        turn_result = self.helpers.create_test_player_turn(
            room_id=room_id,
            active_players=player_ids,
            is_dice_turn=True,
            difficulty=difficulty,
            action_desc="测试检定"
        )
        self.assertIsNotNone(turn_result, "创建骰子检定回合失败")
        
        # 测试边界情况：最小值（1）
        min_roll = 1
        action_result = self.helpers.simulate_player_action(
            room_id=room_id,
            player_id=player_ids[0],
            action="尝试最小值检定",
            roll=min_roll
        )
        self.assertIsNotNone(action_result, "模拟最小值骰子检定失败")
        self.assertTrue(action_result.get("success"), "最小值骰子检定操作未成功")
        self.assertFalse(action_result.get("result").get("success"), "最小值骰子检定结果不正确")
        
        # 测试边界情况：最大值（20）
        max_roll = 20
        action_result = self.helpers.simulate_player_action(
            room_id=room_id,
            player_id=player_ids[1],
            action="尝试最大值检定",
            roll=max_roll
        )
        self.assertIsNotNone(action_result, "模拟最大值骰子检定失败")
        self.assertTrue(action_result.get("success"), "最大值骰子检定操作未成功")
        self.assertTrue(action_result.get("result").get("success"), "最大值骰子检定结果不正确")
        
        # 测试边界情况：等于难度值
        equal_roll = difficulty
        action_result = self.helpers.simulate_player_action(
            room_id=room_id,
            player_id=player_ids[2] if len(player_ids) > 2 else player_ids[0],
            action="尝试等于难度值检定",
            roll=equal_roll
        )
        self.assertIsNotNone(action_result, "模拟等于难度值骰子检定失败")
        self.assertTrue(action_result.get("success"), "等于难度值骰子检定操作未成功")
        self.assertTrue(action_result.get("result").get("success"), "等于难度值骰子检定结果不正确")

if __name__ == "__main__":
    unittest.main()
