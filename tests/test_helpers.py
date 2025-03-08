from typing import Dict, List, Any, Optional, Tuple
import logging
import time
from tests.api_client import ApiClient

class TestHelpers:
    """测试辅助类，提供常用的测试辅助函数"""
    
    def __init__(self, api_client: ApiClient):
        """初始化测试辅助类
        
        Args:
            api_client: API客户端实例
        """
        self.api_client = api_client
        self.logger = logging.getLogger(__name__)
    
    def reset_server_state(self) -> bool:
        """重置服务器状态
        
        Returns:
            bool: 是否成功
        """
        try:
            result = self.api_client.reset_game_state()
            return result.get("success", False)
        except Exception as e:
            self.logger.exception(f"重置服务器状态失败: {str(e)}")
            return False
    
    def create_test_room(self, name: str = "测试房间", player_count: int = 3, all_ready: bool = False) -> Optional[Dict[str, Any]]:
        """创建测试房间
        
        Args:
            name: 房间名称
            player_count: 玩家数量
            all_ready: 是否所有玩家都准备
            
        Returns:
            Optional[Dict[str, Any]]: 创建的房间信息，失败时返回None
        """
        try:
            return self.api_client.create_test_room(name, player_count, all_ready)
        except Exception as e:
            self.logger.exception(f"创建测试房间失败: {str(e)}")
            return None
    
    def create_test_game(self, room_id: str, scenario_id: str = "asylum", scene: str = "默认场景") -> Optional[Dict[str, Any]]:
        """创建测试游戏
        
        Args:
            room_id: 房间ID
            scenario_id: 剧本ID
            scene: 场景名称
            
        Returns:
            Optional[Dict[str, Any]]: 创建的游戏信息，失败时返回None
        """
        try:
            return self.api_client.create_test_game(room_id, scenario_id, scene)
        except Exception as e:
            self.logger.exception(f"创建测试游戏失败: {str(e)}")
            return None
    
    def create_test_dm_turn(self, room_id: str, narration: str = "这是一个测试DM回合") -> Optional[Dict[str, Any]]:
        """创建测试DM回合
        
        Args:
            room_id: 房间ID
            narration: DM叙述内容
            
        Returns:
            Optional[Dict[str, Any]]: 创建的回合信息，失败时返回None
        """
        try:
            return self.api_client.create_test_turn(
                room_id=room_id,
                turn_type="DM",
                narration=narration
            )
        except Exception as e:
            self.logger.exception(f"创建测试DM回合失败: {str(e)}")
            return None
    
    def create_test_player_turn(self, room_id: str, active_players: Optional[List[str]] = None, 
                               is_dice_turn: bool = False, difficulty: int = 10, 
                               action_desc: str = "测试检定") -> Optional[Dict[str, Any]]:
        """创建测试玩家回合
        
        Args:
            room_id: 房间ID
            active_players: 活跃玩家ID列表
            is_dice_turn: 是否为骰子检定回合
            difficulty: 骰子检定难度
            action_desc: 骰子检定行动描述
            
        Returns:
            Optional[Dict[str, Any]]: 创建的回合信息，失败时返回None
        """
        try:
            kwargs = {
                "active_players": active_players
            }
            
            if is_dice_turn:
                kwargs["is_dice_turn"] = True
                kwargs["difficulty"] = difficulty
                kwargs["action_desc"] = action_desc
            
            return self.api_client.create_test_turn(
                room_id=room_id,
                turn_type="PLAYER",
                **kwargs
            )
        except Exception as e:
            self.logger.exception(f"创建测试玩家回合失败: {str(e)}")
            return None
    
    def simulate_player_action(self, room_id: str, player_id: str, action: str, 
                              roll: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """模拟玩家行动
        
        Args:
            room_id: 房间ID
            player_id: 玩家ID
            action: 行动内容
            roll: 掷骰结果（可选，仅在骰子检定回合有效）
            
        Returns:
            Optional[Dict[str, Any]]: 模拟结果，失败时返回None
        """
        try:
            return self.api_client.simulate_player_action(room_id, player_id, action, roll)
        except Exception as e:
            self.logger.exception(f"模拟玩家行动失败: {str(e)}")
            return None
    
    def simulate_dm_turn(self, room_id: str, narration: str, next_turn_type: str = "PLAYER", 
                        active_players: Optional[List[str]] = None, is_dice_turn: bool = False, 
                        difficulty: int = 10, action_desc: str = "测试检定") -> Optional[Dict[str, Any]]:
        """模拟DM回合
        
        Args:
            room_id: 房间ID
            narration: DM叙述内容
            next_turn_type: 下一回合类型
            active_players: 下一回合激活的玩家ID列表
            is_dice_turn: 下一回合是否为骰子检定回合
            difficulty: 骰子检定难度
            action_desc: 骰子检定行动描述
            
        Returns:
            Optional[Dict[str, Any]]: 模拟结果，失败时返回None
        """
        try:
            return self.api_client.simulate_dm_turn(
                room_id=room_id,
                narration=narration,
                next_turn_type=next_turn_type,
                active_players=active_players,
                is_dice_turn=is_dice_turn,
                difficulty=difficulty,
                action_desc=action_desc
            )
        except Exception as e:
            self.logger.exception(f"模拟DM回合失败: {str(e)}")
            return None
    
    def setup_complete_game(self, room_name: str = "测试房间", player_count: int = 3, 
                           scenario_id: str = "asylum", scene: str = "默认场景") -> Tuple[Optional[str], Optional[str], List[str]]:
        """设置完整的游戏环境，包括创建房间、游戏和初始回合
        
        Args:
            room_name: 房间名称
            player_count: 玩家数量
            scenario_id: 剧本ID
            scene: 场景名称
            
        Returns:
            Tuple[Optional[str], Optional[str], List[str]]: (房间ID, 游戏ID, 玩家ID列表)，失败时相应值为None
        """
        # 重置服务器状态
        if not self.reset_server_state():
            self.logger.error("重置服务器状态失败")
            return None, None, []
        
        # 创建测试房间
        room_result = self.create_test_room(room_name, player_count, True)
        if not room_result:
            self.logger.error("创建测试房间失败")
            return None, None, []
        
        room_id = room_result.get("id")
        player_ids = [p.get("id") for p in room_result.get("players", [])]
        
        # 创建测试游戏
        game_result = self.create_test_game(room_id, scenario_id, scene)
        if not game_result:
            self.logger.error("创建测试游戏失败")
            return room_id, None, player_ids
        
        match_id = game_result.get("match_id")
        
        # 创建初始DM回合
        turn_result = self.create_test_dm_turn(room_id, "游戏开始，欢迎来到测试世界！")
        if not turn_result:
            self.logger.error("创建初始DM回合失败")
        
        return room_id, match_id, player_ids
    
    def wait_for_turn_completion(self, room_id: str, timeout: int = 30) -> bool:
        """等待当前回合完成
        
        Args:
            room_id: 房间ID
            timeout: 超时时间（秒）
            
        Returns:
            bool: 是否成功等待回合完成
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # 获取房间详情
                room = self.api_client.get_room(room_id)
                if not room or not room.get("current_match"):
                    return False
                
                # 获取游戏状态
                game_state = self.api_client.get_debug_game_state()
                if not game_state:
                    return False
                
                # 查找当前回合
                for room_info in game_state.get("rooms", []):
                    if room_info.get("id") == room_id:
                        for match in room_info.get("matches", []):
                            if match.get("id") == room.get("current_match").get("id"):
                                for turn in match.get("turns", []):
                                    if turn.get("id") == match.get("current_turn_id"):
                                        if turn.get("status") == "COMPLETED":
                                            return True
                
                # 等待一段时间再检查
                time.sleep(1)
            except Exception as e:
                self.logger.exception(f"等待回合完成时发生异常: {str(e)}")
                return False
        
        self.logger.error(f"等待回合完成超时")
        return False
    
    def run_complete_game_cycle(self, room_id: str, player_ids: List[str]) -> bool:
        """运行完整的游戏循环，包括DM回合和玩家回合
        
        Args:
            room_id: 房间ID
            player_ids: 玩家ID列表
            
        Returns:
            bool: 是否成功运行完整循环
        """
        try:
            # 模拟DM回合
            dm_result = self.simulate_dm_turn(
                room_id=room_id,
                narration="这是DM的叙述，描述了当前场景和情况。",
                active_players=player_ids
            )
            if not dm_result:
                self.logger.error("模拟DM回合失败")
                return False
            
            # 模拟所有玩家行动
            for player_id in player_ids:
                action_result = self.simulate_player_action(
                    room_id=room_id,
                    player_id=player_id,
                    action=f"玩家{player_id}的行动"
                )
                if not action_result:
                    self.logger.error(f"模拟玩家{player_id}行动失败")
                    return False
            
            # 等待回合完成
            if not self.wait_for_turn_completion(room_id):
                self.logger.error("等待回合完成失败")
                return False
            
            # 模拟骰子检定回合
            dm_result = self.simulate_dm_turn(
                room_id=room_id,
                narration="这是需要进行骰子检定的场景。",
                active_players=player_ids,
                is_dice_turn=True,
                difficulty=10,
                action_desc="攀爬检定"
            )
            if not dm_result:
                self.logger.error("模拟骰子检定DM回合失败")
                return False
            
            # 模拟所有玩家骰子检定
            for player_id in player_ids:
                action_result = self.simulate_player_action(
                    room_id=room_id,
                    player_id=player_id,
                    action=f"玩家{player_id}尝试攀爬",
                    roll=15  # 假设掷出15点
                )
                if not action_result:
                    self.logger.error(f"模拟玩家{player_id}骰子检定失败")
                    return False
            
            # 等待回合完成
            if not self.wait_for_turn_completion(room_id):
                self.logger.error("等待骰子检定回合完成失败")
                return False
            
            return True
        except Exception as e:
            self.logger.exception(f"运行完整游戏循环时发生异常: {str(e)}")
            return False
