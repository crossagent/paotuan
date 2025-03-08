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

class TestRoomManagement(unittest.TestCase):
    """房间管理相关测试"""
    
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
    
    def test_create_room(self):
        """测试创建房间"""
        # 创建房间
        room_name = "测试房间"
        result = self.api_client.create_room(room_name)
        
        # 验证结果
        self.assertIsNotNone(result, "创建房间失败")
        self.assertEqual(result.get("name"), room_name, "房间名称不匹配")
        self.assertEqual(result.get("player_count"), 1, "房间玩家数量不正确")
        
        # 获取房间列表
        rooms = self.api_client.list_rooms()
        self.assertEqual(len(rooms), 1, "房间列表数量不正确")
        self.assertEqual(rooms[0].get("id"), result.get("id"), "房间ID不匹配")
    
    def test_join_leave_room(self):
        """测试加入和离开房间"""
        # 创建测试房间
        room_result = self.helpers.create_test_room("测试房间", 1, False)
        self.assertIsNotNone(room_result, "创建测试房间失败")
        room_id = room_result.get("id")
        
        # 加入房间
        join_result = self.api_client.join_room(room_id)
        self.assertIsNotNone(join_result, "加入房间失败")
        
        # 验证房间状态
        room = self.api_client.get_room(room_id)
        self.assertEqual(len(room.get("players")), 2, "房间玩家数量不正确")
        
        # 离开房间
        leave_result = self.api_client.leave_room(room_id)
        self.assertIsNotNone(leave_result, "离开房间失败")
        self.assertTrue(leave_result.get("success"), "离开房间操作未成功")
        
        # 验证房间状态
        room = self.api_client.get_room(room_id)
        self.assertEqual(len(room.get("players")), 1, "房间玩家数量不正确")
    
    def test_player_ready(self):
        """测试玩家准备状态"""
        # 创建测试房间
        room_result = self.helpers.create_test_room("测试房间", 2, False)
        self.assertIsNotNone(room_result, "创建测试房间失败")
        room_id = room_result.get("id")
        
        # 加入房间
        join_result = self.api_client.join_room(room_id)
        self.assertIsNotNone(join_result, "加入房间失败")
        
        # 设置准备状态
        ready_result = self.api_client.set_ready(room_id, True)
        self.assertIsNotNone(ready_result, "设置准备状态失败")
        self.assertTrue(ready_result.get("is_ready"), "准备状态设置失败")
        
        # 验证房间状态
        room = self.api_client.get_room(room_id)
        current_player = None
        for player in room.get("players"):
            if player.get("id") == "test_user":  # 假设当前用户ID为test_user
                current_player = player
                break
        
        self.assertIsNotNone(current_player, "未找到当前玩家")
        self.assertTrue(current_player.get("is_ready"), "玩家准备状态不正确")
        
        # 取消准备状态
        ready_result = self.api_client.set_ready(room_id, False)
        self.assertIsNotNone(ready_result, "取消准备状态失败")
        self.assertFalse(ready_result.get("is_ready"), "准备状态取消失败")
    
    def test_max_players(self):
        """测试房间最大玩家数限制"""
        # 创建最大玩家数为2的房间
        room_name = "测试房间"
        max_players = 2
        result = self.api_client.create_room(room_name, max_players)
        
        # 验证结果
        self.assertIsNotNone(result, "创建房间失败")
        self.assertEqual(result.get("max_players"), max_players, "最大玩家数设置不正确")
        
        # 添加一个测试玩家
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
    
    def test_host_transfer(self):
        """测试房主转移"""
        # 重置游戏状态
        self.helpers.reset_server_state()
        
        # 当前测试用例已经以test_user身份登录
        
        # 1. test_user创建房间（自动成为房主）
        room_result = self.api_client.create_room("测试房间")
        self.assertIsNotNone(room_result, "创建房间失败")
        room_id = room_result.get("id")
        
        # 2. 获取房间详情，确认test_user是房主
        room = self.api_client.get_room(room_id)
        original_host_id = room.get("host_id")
        self.assertIsNotNone(original_host_id, "未找到房主ID")
        
        # 3. 创建并登录test_player_1
        player_api_client = ApiClient()
        success = player_api_client.login("test_player_1", "password")
        self.assertTrue(success, "test_player_1登录失败")
        
        # 4. test_player_1加入房间
        join_result = player_api_client.join_room(room_id)
        self.assertIsNotNone(join_result, "test_player_1加入房间失败")
        
        # 5. 确认房间现在有两个玩家
        room = self.api_client.get_room(room_id)
        self.assertEqual(len(room.get("players", [])), 2, "房间玩家数量不正确")
        
        # 6. test_user（房主）离开房间
        leave_result = self.api_client.leave_room(room_id)
        self.assertIsNotNone(leave_result, "房主离开房间失败")
        self.assertTrue(leave_result.get("success"), "房主离开房间操作未成功")
        
        # 7. 验证房主已转移到test_player_1
        room = player_api_client.get_room(room_id)
        new_host_id = room.get("host_id")
        self.assertIsNotNone(new_host_id, "未找到新房主ID")
        self.assertNotEqual(new_host_id, original_host_id, "房主未转移")

if __name__ == "__main__":
    unittest.main()
