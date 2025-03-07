import asyncio
import logging
import uuid
import re
from typing import Dict, List, Optional, Any
from datetime import datetime

# 导入必要组件
from core.game_state import GameState
from core.events import EventBus
from core.rules import RuleEngine
from services.ai_service import AIService
from services.game_state_service import GameStateService
from services.game_coordinator import GameCoordinator
from models.entities import GameStatus, TurnType, TurnStatus
from adapters.base import (
    GameEvent, CreateRoomEvent, JoinRoomEvent, SetScenarioEvent,
    SelectCharacterEvent, StartMatchEvent, PlayerActionEvent, 
    DMNarrationEvent, EndMatchEvent, PlayerJoinedEvent
)
from utils.scenario_loader import ScenarioLoader

class TestAdapter:
    """测试适配器，用于模拟消息交互"""
    
    def __init__(self, coordinator):
        self.coordinator = coordinator
        self.events = []
        self.responses = []
        
    async def send_event(self, event):
        """发送事件到协调器并收集响应"""
        print(f"\n[发送事件] {event.event_type}: {event.data}")
        self.events.append(event)
        await self.coordinator._process_event(event)
        
    async def collect_response(self, timeout=0.5):
        """等待并收集响应消息"""
        await asyncio.sleep(timeout)  # 给系统一些处理时间
        responses = self.responses.copy()
        self.responses.clear()
        return responses
        
    async def receive_message(self):
        """Mock receive_message 方法"""
        if self.events:
            return self.events.pop(0)
        return None
        
    async def send_message(self, player_id, content):
        """记录发送的消息"""
        self.responses.append({"recipient": player_id, "content": content})
        print(f"[发送到玩家 {player_id}]: {content[:100]}{'...' if len(content) > 100 else ''}")
        
    async def start(self):
        """启动适配器"""
        pass
        
    async def stop(self):
        """停止适配器"""
        pass

class GameStateTester:
    """游戏状态测试辅助类，用于验证系统状态"""
    
    def __init__(self, coordinator: GameCoordinator):
        self.coordinator = coordinator
        self.game_state = coordinator.game_state
        
    def verify_room_created(self, room_id: str) -> bool:
        """验证房间是否创建成功"""
        room = self.game_state.get_room(room_id)
        if not room:
            print(f"[验证失败] 房间 {room_id} 不存在")
            return False
        print(f"[验证成功] 房间 {room_id} 已创建")
        return True
        
    def verify_player_in_room(self, player_id: str, room_id: str) -> bool:
        """验证玩家是否在房间中"""
        room = self.game_state.get_room(room_id)
        if not room:
            print(f"[验证失败] 房间 {room_id} 不存在")
            return False
            
        player_in_room = False
        for player in room.players:
            if player.id == player_id:
                player_in_room = True
                break
                
        if not player_in_room:
            print(f"[验证失败] 玩家 {player_id} 不在房间 {room_id} 中")
            return False
            
        print(f"[验证成功] 玩家 {player_id} 在房间 {room_id} 中")
        return True
        
    def verify_scenario_set(self, room_id: str, scenario_id: str) -> bool:
        """验证剧本是否已设置"""
        room = self.game_state.get_room(room_id)
        if not room or not room.current_match_id:
            print(f"[验证失败] 房间 {room_id} 没有当前游戏局")
            return False
            
        match = None
        for m in room.matches:
            if m.id == room.current_match_id:
                match = m
                break
                
        if not match or match.scenario_id != scenario_id:
            print(f"[验证失败] 游戏局剧本不是 {scenario_id}")
            return False
            
        print(f"[验证成功] 游戏局已设置剧本 {scenario_id}")
        return True
        
    def verify_character_selected(self, player_id: str, character_name: str) -> bool:
        """验证角色是否已选择"""
        # 获取玩家信息
        player_room = self.game_state.get_player_room(player_id)
        if not player_room or not player_room.current_match_id:
            print(f"[验证失败] 玩家 {player_id} 不在游戏局中")
            return False
            
        # 获取玩家
        player = None
        for p in player_room.players:
            if p.id == player_id:
                player = p
                break
                
        if not player or not player.character_id:
            print(f"[验证失败] 玩家 {player_id} 未选择角色")
            return False
            
        # 获取游戏局
        match = None
        for m in player_room.matches:
            if m.id == player_room.current_match_id:
                match = m
                break
                
        if not match:
            print(f"[验证失败] 找不到当前游戏局")
            return False
            
        # 验证角色
        character = None
        for c in match.characters:
            if c.id == player.character_id:
                character = c
                break
                
        if not character or character.name != character_name:
            print(f"[验证失败] 玩家 {player_id} 的角色不是 {character_name}")
            return False
            
        print(f"[验证成功] 玩家 {player_id} 已选择角色 {character_name}")
        return True
        
    def verify_game_started(self, room_id: str) -> bool:
        """验证游戏是否已开始"""
        room = self.game_state.get_room(room_id)
        if not room or not room.current_match_id:
            print(f"[验证失败] 房间 {room_id} 没有当前游戏局")
            return False
            
        match = None
        for m in room.matches:
            if m.id == room.current_match_id:
                match = m
                break
                
        if not match or match.status != GameStatus.RUNNING:
            print(f"[验证失败] 游戏局状态不是 RUNNING，当前状态: {match.status if match else 'None'}")
            return False
            
        print(f"[验证成功] 游戏已开始")
        return True
        
    def verify_dm_turn_created(self, room_id: str) -> bool:
        """验证DM回合是否已创建"""
        room = self.game_state.get_room(room_id)
        if not room or not room.current_match_id:
            print(f"[验证失败] 房间 {room_id} 没有当前游戏局")
            return False
            
        match = None
        for m in room.matches:
            if m.id == room.current_match_id:
                match = m
                break
                
        if not match or not match.current_turn_id:
            print(f"[验证失败] 游戏局没有当前回合")
            return False
            
        current_turn = None
        for turn in match.turns:
            if turn.id == match.current_turn_id:
                current_turn = turn
                break
                
        if not current_turn or current_turn.turn_type != TurnType.DM:
            print(f"[验证失败] 当前回合不是DM回合，当前类型: {current_turn.turn_type if current_turn else 'None'}")
            return False
            
        print(f"[验证成功] DM回合已创建")
        return True
        
    def verify_player_turn_created(self, room_id: str) -> bool:
        """验证玩家回合是否已创建"""
        room = self.game_state.get_room(room_id)
        if not room or not room.current_match_id:
            print(f"[验证失败] 房间 {room_id} 没有当前游戏局")
            return False
            
        match = None
        for m in room.matches:
            if m.id == room.current_match_id:
                match = m
                break
                
        if not match or not match.current_turn_id:
            print(f"[验证失败] 游戏局没有当前回合")
            return False
            
        current_turn = None
        for turn in match.turns:
            if turn.id == match.current_turn_id:
                current_turn = turn
                break
                
        if not current_turn or current_turn.turn_type != TurnType.PLAYER:
            print(f"[验证失败] 当前回合不是玩家回合，当前类型: {current_turn.turn_type if current_turn else 'None'}")
            return False
            
        print(f"[验证成功] 玩家回合已创建")
        return True
        
    def verify_game_ended(self, room_id: str) -> bool:
        """验证游戏是否已结束"""
        room = self.game_state.get_room(room_id)
        if not room or not room.current_match_id:
            print(f"[验证失败] 房间 {room_id} 没有当前游戏局")
            return False
            
        match = None
        for m in room.matches:
            if m.id == room.current_match_id:
                match = m
                break
                
        if not match or match.status != GameStatus.FINISHED:
            print(f"[验证失败] 游戏局状态不是 FINISHED，当前状态: {match.status if match else 'None'}")
            return False
            
        print(f"[验证成功] 游戏已结束")
        return True
        
    def dump_game_state(self):
        """输出当前游戏状态"""
        print("\n=== 当前游戏状态 ===")
        
        # 输出房间信息
        rooms = self.game_state.list_rooms()
        print(f"房间数量: {len(rooms)}")
        
        for room in rooms:
            print(f"\n房间: {room.name} (ID: {room.id})")
            print(f"  玩家数量: {len(room.players)}")
            
            for player in room.players:
                print(f"  - 玩家: {player.name} (ID: {player.id})")
                print(f"    角色ID: {player.character_id}")
                print(f"    准备状态: {'已准备' if player.is_ready else '未准备'}")
                print(f"    房主: {'是' if player.is_host else '否'}")
                
            print(f"  游戏局数量: {len(room.matches)}")
            
            for match in room.matches:
                print(f"  - 游戏局 (ID: {match.id})")
                print(f"    状态: {match.status}")
                print(f"    剧本: {match.scenario_id}")
                print(f"    角色数量: {len(match.characters)}")
                
                for character in match.characters:
                    print(f"    - 角色: {character.name} (ID: {character.id})")
                    print(f"      玩家ID: {character.player_id}")
                    print(f"      生命值: {character.health}")
                    print(f"      存活状态: {'存活' if character.alive else '死亡'}")
                    
                print(f"    回合数量: {len(match.turns)}")
                
                for turn in match.turns:
                    print(f"    - 回合 (ID: {turn.id})")
                    print(f"      类型: {turn.turn_type}")
                    print(f"      状态: {turn.status}")
                    
                if match.current_turn_id:
                    print(f"    当前回合ID: {match.current_turn_id}")
        
        print("=== 游戏状态输出结束 ===\n")

async def run_event_test():
    """使用模拟事件测试游戏流程"""
    # 初始化组件
    game_state = GameState("test_game")
    event_bus = EventBus()
    rule_engine = RuleEngine()
    ai_service = AIService()  # 可能需要一个模拟的AI服务
    scenario_loader = ScenarioLoader()
    
    # 创建协调器
    coordinator = GameCoordinator(ai_service)
    
    # 创建测试适配器
    test_adapter = TestAdapter(coordinator)
    coordinator.register_adapter(test_adapter)
    
    # 创建状态测试器
    state_tester = GameStateTester(coordinator)
    
    # 启动协调器
    await coordinator.start()
    
    # 打印测试开始
    print("=== 开始模拟事件测试 ===")
    
    # 测试状态记录
    test_state = {
        "host_id": "host_" + str(uuid.uuid4())[:8],
        "host_name": "房主",
        "player_ids": [
            "player_" + str(uuid.uuid4())[:8],
            "player_" + str(uuid.uuid4())[:8]
        ],
        "player_names": ["玩家1", "玩家2"],
        "room_id": None,
        "scenario_id": "asylum",  # 使用已有的剧本ID
        "characters": ["侦探", "医生", "警察"]
    }
    
    try:
        # 测试流程开始
        print("\n\n==== 1. 房间准备阶段 ====")
        
        # 1.1 创建房间
        print("\n--- 1.1 创建房间 ---")
        create_room_event = CreateRoomEvent(
            player_id=test_state["host_id"],
            room_name="测试房间"
        )
        await test_adapter.send_event(create_room_event)
        responses = await test_adapter.collect_response()
        
        # 从响应中提取房间ID
        room_id_found = False
        for resp in responses:
            if resp["recipient"] == test_state["host_id"] and "成功创建房间" in resp["content"]:
                # 从消息中解析房间ID
                match = re.search(r"ID: ([\w-]+)", resp["content"])
                if match:
                    test_state["room_id"] = match.group(1)
                    print(f"获取到房间ID: {test_state['room_id']}")
                    room_id_found = True
                    break
        
        if not room_id_found:
            raise ValueError("创建房间失败，无法获取房间ID")
            
        # 验证房间创建
        assert state_tester.verify_room_created(test_state["room_id"]), "房间创建验证失败"
        
        # 1.2 玩家加入房间
        print("\n--- 1.2 玩家加入房间 ---")
        for i, player_id in enumerate(test_state["player_ids"]):
            join_room_event = JoinRoomEvent(
                player_id=player_id,
                player_name=test_state["player_names"][i],
                room_id=test_state["room_id"]
            )
            await test_adapter.send_event(join_room_event)
            await test_adapter.collect_response()
            print(f"玩家 {test_state['player_names'][i]} (ID: {player_id}) 尝试加入房间")
            
            # 验证玩家加入
            assert state_tester.verify_player_in_room(player_id, test_state["room_id"]), f"玩家 {player_id} 加入房间验证失败"
        
        # 输出当前游戏状态
        state_tester.dump_game_state()
        
        print("\n\n==== 2. 角色选择阶段 ====")
        
        # 2.1 设置剧本
        print("\n--- 2.1 设置剧本 ---")
        set_scenario_event = SetScenarioEvent(
            player_id=test_state["host_id"],
            scenario_id=test_state["scenario_id"]
        )
        await test_adapter.send_event(set_scenario_event)
        await test_adapter.collect_response()
        print(f"房主设置剧本: {test_state['scenario_id']}")
        
        # 验证剧本设置
        assert state_tester.verify_scenario_set(test_state["room_id"], test_state["scenario_id"]), "剧本设置验证失败"
        
        # 2.2 玩家选择角色
        print("\n--- 2.2 玩家选择角色 ---")
        # 获取可用角色
        available_characters = scenario_loader.load_character_templates(test_state["scenario_id"])
        if available_characters:
            print(f"获取到可用角色: {[char.name for char in available_characters]}")
            test_state["characters"] = [char.name for char in available_characters[:3]]
        
        for i, player_id in enumerate(test_state["player_ids"]):
            character_index = i % len(test_state["characters"])  # 循环使用角色列表
            character_name = test_state["characters"][character_index]
            
            select_character_event = SelectCharacterEvent(
                player_id=player_id,
                character_name=character_name
            )
            await test_adapter.send_event(select_character_event)
            await test_adapter.collect_response()
            print(f"玩家 {test_state['player_names'][i]} (ID: {player_id}) 选择角色 {character_name}")
            
            # 验证角色选择
            assert state_tester.verify_character_selected(player_id, character_name), f"玩家 {player_id} 选择角色验证失败"
        
        # 房主也选择角色
        host_character = test_state["characters"][-1]  # 选择最后一个角色
        select_character_event = SelectCharacterEvent(
            player_id=test_state["host_id"],
            character_name=host_character
        )
        await test_adapter.send_event(select_character_event)
        await test_adapter.collect_response()
        print(f"房主 (ID: {test_state['host_id']}) 选择角色 {host_character}")
        
        # 验证角色选择
        assert state_tester.verify_character_selected(test_state["host_id"], host_character), f"房主角色选择验证失败"
        
        # 输出当前游戏状态
        state_tester.dump_game_state()
        
        print("\n\n==== 3. 游戏执行阶段 ====")
        
        # 3.1 开始游戏
        print("\n--- 3.1 开始游戏 ---")
        start_match_event = StartMatchEvent(
            player_id=test_state["host_id"],
            player_name=test_state["host_name"]
        )
        await test_adapter.send_event(start_match_event)
        await test_adapter.collect_response()
        print("房主开始游戏")
        
        # 验证游戏开始
        assert state_tester.verify_game_started(test_state["room_id"]), "游戏开始验证失败"
        
        # 输出当前游戏状态
        state_tester.dump_game_state()
        
        # 3.2 DM回合 - 场景描述
        print("\n--- 3.2 DM回合 - 场景描述 ---")
        dm_narration_event = DMNarrationEvent(
            narration="你们发现自己在一个阴暗的房间中醒来，周围是斑驳的墙壁和锈迹斑斑的金属门。空气中弥漫着一股霉味...",
            room_id=test_state["room_id"]
        )
        await test_adapter.send_event(dm_narration_event)
        await test_adapter.collect_response()
        print("DM描述场景")
        
        # 验证DM回合创建
        assert state_tester.verify_dm_turn_created(test_state["room_id"]), "DM回合创建验证失败"
        
        # 输出当前游戏状态
        state_tester.dump_game_state()
        
        # 3.3 玩家回合 - 普通行动
        print("\n--- 3.3 玩家回合 - 普通行动 ---")
        
        # 验证是否转换到玩家回合
        assert state_tester.verify_player_turn_created(test_state["room_id"]), "玩家回合创建验证失败"
        
        for i, player_id in enumerate(test_state["player_ids"]):
            player_action_event = PlayerActionEvent(
                player_id=player_id,
                action="我环顾四周，查看有没有可以使用的物品或者线索。"
            )
            await test_adapter.send_event(player_action_event)
            await test_adapter.collect_response()
            print(f"玩家 {test_state['player_names'][i]} (ID: {player_id}) 执行普通行动")
        
        # 房主也执行行动
        player_action_event = PlayerActionEvent(
            player_id=test_state["host_id"],
            action="我尝试打开房间的门，看看是否被锁住了。"
        )
        await test_adapter.send_event(player_action_event)
        await test_adapter.collect_response()
        print(f"房主 (ID: {test_state['host_id']}) 执行普通行动")
        
        # 输出当前游戏状态
        state_tester.dump_game_state()
        
        # 3.4 再次DM回合 - 指定进行骰子检定
        print("\n--- 3.4 再次DM回合 - 指定骰子检定 ---")
        dm_narration_event = DMNarrationEvent(
            narration="门似乎被锁住了。你需要进行一次力量检定才能尝试破门而出。",
            room_id=test_state["room_id"]
        )
        await test_adapter.send_event(dm_narration_event)
        await test_adapter.collect_response()
        print("DM要求力量检定")
        
        # 验证DM回合创建
        assert state_tester.verify_dm_turn_created(test_state["room_id"]), "第二个DM回合创建验证失败"
        
        # 输出当前游戏状态
        state_tester.dump_game_state()
        
        print("\n\n==== 4. 游戏结束阶段 ====")
        
        # 4.1 结束游戏
        print("\n--- 4.1 结束游戏 ---")
        end_match_event = EndMatchEvent(
            player_id=test_state["host_id"],
            player_name=test_state["host_name"],
            result="测试完成"
        )
        await test_adapter.send_event(end_match_event)
        await test_adapter.collect_response()
        print("房主结束游戏")
        
        # 验证游戏结束
        assert state_tester.verify_game_ended(test_state["room_id"]), "游戏结束验证失败"
        
        # 输出最终游戏状态
        state_tester.dump_game_state()
        
        print("\n=== 测试全部通过！ ===")
    except AssertionError as e:
        print(f"\n[测试失败] {str(e)}")
    except Exception as e:
        print(f"\n[测试错误] {str(e)}")
    finally:
        # 停止协调器
        await coordinator.stop()
        print("\n=== 测试结束 ===")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_event_test())
