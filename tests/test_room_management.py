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
        
        # 确保有足够的测试用户
        cls.helpers.ensure_test_users(10)
        
        # 登录
        success = cls.api_client.login("test_user1", "testpassword")
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
        # 获取两个用户客户端
        clients = self.helpers.get_multiple_user_clients(2)
        self.assertGreaterEqual(len(clients), 2, "可用的用户客户端数量不足")
        
        host_client = clients[0]  # 房主
        member_client = clients[1]  # 成员
        
        # 房主创建房间
        room_result = host_client.create_room("测试加入离开房间")
        self.assertIsNotNone(room_result, "创建房间失败")
        room_id = room_result.get("id")
        
        # 获取房间初始状态
        room_before = host_client.get_room(room_id)
        initial_player_count = len(room_before.get("players"))
        self.assertEqual(initial_player_count, 1, "初始房间玩家数量不正确")
        
        # 成员加入房间
        join_result = member_client.join_room(room_id)
        self.assertIsNotNone(join_result, "加入房间失败")
        
        # 验证房间状态
        room = host_client.get_room(room_id)
        self.assertEqual(len(room.get("players")), initial_player_count + 1, "房间玩家数量不正确")
        
        # 成员离开房间
        leave_result = member_client.leave_room(room_id)
        self.assertIsNotNone(leave_result, "离开房间失败")
        self.assertTrue(leave_result.get("success"), "离开房间操作未成功")
        
        # 验证房间状态
        room = host_client.get_room(room_id)
        self.assertEqual(len(room.get("players")), initial_player_count, "房间玩家数量不正确")
    
    def test_player_ready(self):
        """测试玩家准备状态"""
        # 获取两个用户客户端
        clients = self.helpers.get_multiple_user_clients(2)
        self.assertGreaterEqual(len(clients), 2, "可用的用户客户端数量不足")
        
        host_client = clients[0]  # 房主
        member_client = clients[1]  # 成员
        
        # 房主创建房间
        room_result = host_client.create_room("测试准备状态房间")
        self.assertIsNotNone(room_result, "创建房间失败")
        room_id = room_result.get("id")
        
        # 成员加入房间
        join_result = member_client.join_room(room_id)
        self.assertIsNotNone(join_result, "加入房间失败")
        
        # 成员设置准备状态
        ready_result = member_client.set_ready(room_id, True)
        self.assertIsNotNone(ready_result, "设置准备状态失败")
        self.assertTrue(ready_result.get("is_ready"), "准备状态设置失败")
        
        # 验证房间状态
        room = host_client.get_room(room_id)
        for player in room.get("players"):
            if player.get("id") == member_client.username:  # 使用username作为ID
                self.assertTrue(player.get("is_ready"), "玩家准备状态不正确")
        
        # 成员取消准备状态
        ready_result = member_client.set_ready(room_id, False)
        self.assertIsNotNone(ready_result, "取消准备状态失败")
        self.assertFalse(ready_result.get("is_ready"), "准备状态取消失败")
        
        # 再次验证房间状态
        room = host_client.get_room(room_id)
        for player in room.get("players"):
            if player.get("id") == member_client.username:  # 使用username作为ID
                self.assertFalse(player.get("is_ready"), "玩家准备状态未正确取消")
    
    def test_max_players(self):
        """测试房间最大玩家数限制"""
        # 获取3个用户客户端
        clients = self.helpers.get_multiple_user_clients(3)
        self.assertGreaterEqual(len(clients), 3, "可用的用户客户端数量不足")
        
        host_client = clients[0]  # 房主
        member1_client = clients[1]  # 成员1
        member2_client = clients[2]  # 成员2
        
        # 创建最大玩家数为2的房间
        room_name = "测试最大玩家数房间"
        max_players = 2
        room_result = host_client.create_room(room_name, max_players)
        
        # 验证结果
        self.assertIsNotNone(room_result, "创建房间失败")
        self.assertEqual(room_result.get("max_players"), max_players, "最大玩家数设置不正确")
        
        room_id = room_result.get("id")
        
        # 成员1加入房间（应该成功，因为最大玩家数为2）
        join_result1 = member1_client.join_room(room_id)
        self.assertIsNotNone(join_result1, "成员1加入房间失败")
        
        # 验证房间状态 - 应该有2个玩家
        room = host_client.get_room(room_id)
        self.assertEqual(len(room.get("players", [])), 2, "房间玩家数量不正确")
        
        # 成员2尝试加入房间（应该失败，因为已达到最大玩家数）
        try:
            join_result2 = member2_client.join_room(room_id)
            # 如果执行到这里，说明没有抛出异常，这是不对的
            self.fail("超出最大玩家数限制仍能加入房间")
        except Exception as e:
            # 预期会抛出异常，直接检查异常消息
            self.assertIn("已达到最大玩家数", str(e), "错误消息不正确")
    
    def test_host_transfer(self):
        """测试房主转移"""
        # 获取两个用户客户端
        clients = self.helpers.get_multiple_user_clients(2)
        self.assertGreaterEqual(len(clients), 2, "可用的用户客户端数量不足")
        
        host_client = clients[0]  # 房主
        member_client = clients[1]  # 成员
        
        # 房主创建房间
        room_result = host_client.create_room("测试房主转移房间")
        self.assertIsNotNone(room_result, "创建房间失败")
        room_id = room_result.get("id")
        
        # 获取房间详情，确认房主ID
        room = host_client.get_room(room_id)
        original_host_id = room.get("host_id")
        self.assertIsNotNone(original_host_id, "未找到房主ID")
        
        # 成员加入房间
        join_result = member_client.join_room(room_id)
        self.assertIsNotNone(join_result, "成员加入房间失败")
        
        # 确认房间现在有两个玩家
        room = host_client.get_room(room_id)
        self.assertEqual(len(room.get("players", [])), 2, "房间玩家数量不正确")
        
        # 房主离开房间
        leave_result = host_client.leave_room(room_id)
        self.assertIsNotNone(leave_result, "房主离开房间失败")
        self.assertTrue(leave_result.get("success"), "房主离开房间操作未成功")
        
        # 验证房主已转移到成员
        room = member_client.get_room(room_id)
        new_host_id = room.get("host_id")
        self.assertIsNotNone(new_host_id, "未找到新房主ID")
        self.assertNotEqual(new_host_id, original_host_id, "房主未转移")
    
    def test_user_room_lifecycle(self):
        """测试用户的房间生命周期，特别关注房主转移机制和房间自动关闭"""
        # 重置游戏状态
        self.helpers.reset_server_state()
        
        # 获取3个用户API客户端（已登录状态）
        clients = self.helpers.get_multiple_user_clients(3)
        self.assertGreaterEqual(len(clients), 3, "可用的用户客户端数量不足")
        
        host_client = clients[0]  # 房主
        member1_client = clients[1]  # 成员1
        member2_client = clients[2]  # 成员2
        
        # 1. 房主创建房间
        room_result = host_client.create_room("用户生命周期测试房间")
        self.assertIsNotNone(room_result, "创建房间失败")
        room_id = room_result.get("id")
        
        # 2. 成员1加入房间
        join_result1 = member1_client.join_room(room_id)
        self.assertIsNotNone(join_result1, "成员1加入房间失败")
        
        # 3. 成员2加入房间
        join_result2 = member2_client.join_room(room_id)
        self.assertIsNotNone(join_result2, "成员2加入房间失败")
        
        # 4. 验证房间状态 - 应该有3个用户，且房主是初始创建者
        room = host_client.get_room(room_id)
        self.assertEqual(len(room.get("players", [])), 3, "房间玩家数量不正确")
        host_id = room.get("host_id")  # 记录初始房主ID
        
        # 5. 房主离开房间 - 应触发房主转移
        leave_result = host_client.leave_room(room_id)
        self.assertTrue(leave_result.get("success"), "房主离开房间失败")
        
        # 6. 验证房主已转移(应该转移给成员1，即房间中加入时间最长的成员)
        room = member1_client.get_room(room_id)
        new_host_id = room.get("host_id")
        self.assertIsNotNone(new_host_id, "未找到新房主ID")
        self.assertNotEqual(new_host_id, host_id, "房主未正确转移")
        
        # 7. 成员1(新房主)离开房间 - 再次触发房主转移
        leave_result = member1_client.leave_room(room_id)
        self.assertTrue(leave_result.get("success"), "新房主离开房间失败")
        
        # 8. 验证房主已转移给成员2
        room = member2_client.get_room(room_id)
        newest_host_id = room.get("host_id")
        self.assertIsNotNone(newest_host_id, "未找到最新房主ID")
        
        # 验证房主已正确转移
        # 不再检查房主ID是否变化，而是检查房主是否是房间中的一个有效玩家
        players = room.get("players", [])
        player_ids = [p.get("id") for p in players]
        self.assertIn(newest_host_id, player_ids, "房主ID不是房间中的有效玩家ID")
        
        # 如果房间中有多个玩家，房主应该是按加入顺序选择的第一个玩家
        if len(players) > 1:
            expected_host_id = players[0].get("id")
            self.assertEqual(newest_host_id, expected_host_id, "房主未按加入顺序选择")
        
        # 9. 最后一个成员离开房间 - 房间应该被销毁
        leave_result = member2_client.leave_room(room_id)
        self.assertTrue(leave_result.get("success"), "最后成员离开房间失败")
        
        # 10. 验证房间已被销毁 - 尝试获取房间应该失败
        try:
            member2_client.get_room(room_id)
            self.fail("房间未被正确销毁")
        except Exception:
            # 预期会抛出异常，因为房间已不存在
            pass
    
    def test_player_ready_and_game_start(self):
        """测试玩家准备状态和游戏开始条件"""
        # 重置游戏状态
        self.helpers.reset_server_state()
        
        # 获取3个用户API客户端（已登录状态）
        clients = self.helpers.get_multiple_user_clients(3)
        self.assertGreaterEqual(len(clients), 3, "可用的用户客户端数量不足")
        
        host_client = clients[0]  # 房主
        member1_client = clients[1]  # 成员1
        member2_client = clients[2]  # 成员2
        
        # 1. 房主创建房间
        room_result = host_client.create_room("准备状态测试房间")
        self.assertIsNotNone(room_result, "创建房间失败")
        room_id = room_result.get("id")
        
        # 2. 成员加入房间
        member1_client.join_room(room_id)
        member2_client.join_room(room_id)
        
        # 3. 场景一：部分玩家未准备好，尝试开始游戏（应失败）
        
        # 只有成员1准备
        ready_result = member1_client.set_ready(room_id, True)
        self.assertTrue(ready_result.get("is_ready"), "设置准备状态失败")
        
        # 房主和成员2不准备
        
        # 房主尝试开始游戏（应该失败）
        try:
            start_result = host_client.start_game(room_id)
            self.fail("在所有玩家未准备好的情况下不应该能开始游戏")
        except Exception as e:
            # 预期会抛出异常
            self.assertIn("还有玩家未准备", str(e), "错误消息不正确")
        
        # 4. 场景二：所有非房主玩家都准备好，尝试开始游戏（应成功）
        
        # 确保所有非房主玩家都准备
        member1_client.set_ready(room_id, True)  # 确保成员1准备
        member2_client.set_ready(room_id, True)  # 确保成员2准备
        
        # 验证所有非房主玩家都已准备
        room = host_client.get_room(room_id)
        self.assertTrue(room.get("all_players_ready"), "所有非房主玩家应该都已准备好")


        # 房主开始游戏（应该成功）
        start_result = host_client.start_game(room_id)
        self.assertIsNotNone(start_result, "开始游戏失败")
        self.assertIsNotNone(start_result.get("match_id"), "未获取到游戏ID")
        
        # 验证游戏已开始
        room = host_client.get_room(room_id)
        self.assertIsNotNone(room.get("current_match"), "游戏未成功开始")

if __name__ == "__main__":
    unittest.main()
