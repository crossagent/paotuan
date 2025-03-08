import requests
import json
from typing import Dict, List, Any, Optional, Union
import logging

class ApiClient:
    """API客户端，用于与游戏服务器API交互"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        """初始化API客户端
        
        Args:
            base_url: API基础URL
        """
        self.base_url = base_url
        self.token = None
        self.logger = logging.getLogger(__name__)
    
    def login(self, username: str, password: str) -> bool:
        """登录并获取认证令牌
        
        Args:
            username: 用户名
            password: 密码
            
        Returns:
            bool: 登录是否成功
        """
        url = f"{self.base_url}/api/users/token"
        data = {
            "username": username,
            "password": password
        }
        
        try:
            response = requests.post(url, data=data)
            if response.status_code == 200:
                result = response.json()
                self.token = result.get("access_token")
                return True
            else:
                self.logger.error(f"登录失败: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            self.logger.exception(f"登录异常: {str(e)}")
            return False
    
    def _get_headers(self) -> Dict[str, str]:
        """获取请求头，包含认证令牌
        
        Returns:
            Dict[str, str]: 请求头字典
        """
        headers = {
            "Content-Type": "application/json"
        }
        
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        
        return headers
    
    def _request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """发送HTTP请求
        
        Args:
            method: HTTP方法（GET, POST, PUT, DELETE等）
            endpoint: API端点路径
            data: 请求数据
            
        Returns:
            Dict[str, Any]: 响应数据
            
        Raises:
            Exception: 请求失败时抛出异常
        """
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, json=data)
            elif method.upper() == "PUT":
                response = requests.put(url, headers=headers, json=data)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=headers)
            else:
                raise ValueError(f"不支持的HTTP方法: {method}")
            
            if response.status_code >= 200 and response.status_code < 300:
                return response.json()
            else:
                error_msg = f"请求失败: {response.status_code} - {response.text}"
                self.logger.error(error_msg)
                raise Exception(error_msg)
        except Exception as e:
            self.logger.exception(f"请求异常: {str(e)}")
            raise
    
    # 房间相关API
    
    def list_rooms(self) -> List[Dict[str, Any]]:
        """获取房间列表
        
        Returns:
            List[Dict[str, Any]]: 房间列表
        """
        return self._request("GET", "/api/rooms/")
    
    def create_room(self, name: str, max_players: int = 6) -> Dict[str, Any]:
        """创建房间
        
        Args:
            name: 房间名称
            max_players: 最大玩家数
            
        Returns:
            Dict[str, Any]: 创建的房间信息
        """
        data = {
            "name": name,
            "max_players": max_players
        }
        return self._request("POST", "/api/rooms/", data)
    
    def get_room(self, room_id: str) -> Dict[str, Any]:
        """获取房间详情
        
        Args:
            room_id: 房间ID
            
        Returns:
            Dict[str, Any]: 房间详情
        """
        return self._request("GET", f"/api/rooms/{room_id}")
    
    def join_room(self, room_id: str) -> Dict[str, Any]:
        """加入房间
        
        Args:
            room_id: 房间ID
            
        Returns:
            Dict[str, Any]: 加入结果
        """
        return self._request("POST", f"/api/rooms/{room_id}/join")
    
    def leave_room(self, room_id: str) -> Dict[str, Any]:
        """离开房间
        
        Args:
            room_id: 房间ID
            
        Returns:
            Dict[str, Any]: 离开结果
        """
        return self._request("POST", f"/api/rooms/{room_id}/leave")
    
    def set_ready(self, room_id: str, is_ready: bool = True) -> Dict[str, Any]:
        """设置准备状态
        
        Args:
            room_id: 房间ID
            is_ready: 是否准备
            
        Returns:
            Dict[str, Any]: 设置结果
        """
        data = {
            "is_ready": is_ready
        }
        return self._request("POST", f"/api/rooms/{room_id}/ready", data)
    
    def start_game(self, room_id: str, scene: str = "默认场景", scenario_id: Optional[str] = None) -> Dict[str, Any]:
        """开始游戏
        
        Args:
            room_id: 房间ID
            scene: 场景名称
            scenario_id: 剧本ID
            
        Returns:
            Dict[str, Any]: 开始游戏结果
        """
        data = {
            "scene": scene
        }
        if scenario_id:
            data["scenario_id"] = scenario_id
        
        return self._request("POST", f"/api/rooms/{room_id}/start", data)
    
    def select_character(self, room_id: str, character_name: str) -> Dict[str, Any]:
        """选择角色
        
        Args:
            room_id: 房间ID
            character_name: 角色名称
            
        Returns:
            Dict[str, Any]: 选择结果
        """
        data = {
            "character_name": character_name
        }
        return self._request("POST", f"/api/rooms/{room_id}/select_character", data)
    
    def set_scenario(self, room_id: str, scenario_id: str) -> Dict[str, Any]:
        """设置剧本
        
        Args:
            room_id: 房间ID
            scenario_id: 剧本ID
            
        Returns:
            Dict[str, Any]: 设置结果
        """
        data = {
            "scenario_id": scenario_id
        }
        return self._request("POST", f"/api/rooms/{room_id}/set_scenario", data)
    
    # 游戏相关API
    
    def get_game_state(self) -> Dict[str, Any]:
        """获取游戏状态
        
        Returns:
            Dict[str, Any]: 游戏状态
        """
        return self._request("GET", "/api/game/state")
    
    def send_action(self, action: str) -> Dict[str, Any]:
        """发送游戏行动
        
        Args:
            action: 行动内容
            
        Returns:
            Dict[str, Any]: 发送结果
        """
        data = {
            "action": action
        }
        return self._request("POST", "/api/game/action", data)
    
    def list_scenarios(self) -> List[Dict[str, Any]]:
        """获取剧本列表
        
        Returns:
            List[Dict[str, Any]]: 剧本列表
        """
        return self._request("GET", "/api/game/scenarios")
    
    def get_scenario(self, scenario_id: str) -> Dict[str, Any]:
        """获取剧本详情
        
        Args:
            scenario_id: 剧本ID
            
        Returns:
            Dict[str, Any]: 剧本详情
        """
        return self._request("GET", f"/api/game/scenarios/{scenario_id}")
    
    # Debug API
    
    def reset_game_state(self) -> Dict[str, Any]:
        """重置游戏状态
        
        Returns:
            Dict[str, Any]: 重置结果
        """
        return self._request("POST", "/api/debug/reset")
    
    def create_test_room(self, name: str = "测试房间", player_count: int = 3, all_ready: bool = False) -> Dict[str, Any]:
        """创建测试房间
        
        Args:
            name: 房间名称
            player_count: 玩家数量
            all_ready: 是否所有玩家都准备
            
        Returns:
            Dict[str, Any]: 创建结果
        """
        data = {
            "name": name,
            "player_count": player_count,
            "all_ready": all_ready
        }
        return self._request("POST", "/api/debug/create_test_room", data)
    
    def create_test_game(self, room_id: str, scenario_id: str = "asylum", scene: str = "默认场景", status: str = "RUNNING") -> Dict[str, Any]:
        """创建测试游戏
        
        Args:
            room_id: 房间ID
            scenario_id: 剧本ID
            scene: 场景名称
            status: 游戏状态
            
        Returns:
            Dict[str, Any]: 创建结果
        """
        data = {
            "room_id": room_id,
            "scenario_id": scenario_id,
            "scene": scene,
            "status": status
        }
        return self._request("POST", "/api/debug/create_test_game", data)
    
    def create_test_turn(self, room_id: str, turn_type: str = "DM", status: str = "PENDING", **kwargs) -> Dict[str, Any]:
        """创建测试回合
        
        Args:
            room_id: 房间ID
            turn_type: 回合类型（DM或PLAYER）
            status: 回合状态（PENDING或COMPLETED）
            **kwargs: 其他参数，根据回合类型不同而不同
            
        Returns:
            Dict[str, Any]: 创建结果
        """
        data = {
            "room_id": room_id,
            "turn_type": turn_type,
            "status": status,
            **kwargs
        }
        return self._request("POST", "/api/debug/create_test_turn", data)
    
    def get_debug_game_state(self) -> Dict[str, Any]:
        """获取完整游戏状态
        
        Returns:
            Dict[str, Any]: 完整游戏状态
        """
        return self._request("GET", "/api/debug/game_state")
    
    def simulate_player_action(self, room_id: str, player_id: str, action: str, roll: Optional[int] = None) -> Dict[str, Any]:
        """模拟玩家行动
        
        Args:
            room_id: 房间ID
            player_id: 玩家ID
            action: 行动内容
            roll: 掷骰结果（可选，仅在骰子检定回合有效）
            
        Returns:
            Dict[str, Any]: 模拟结果
        """
        data = {
            "room_id": room_id,
            "player_id": player_id,
            "action": action
        }
        if roll is not None:
            data["roll"] = roll
        
        return self._request("POST", "/api/debug/simulate_player_action", data)
    
    def simulate_dm_turn(self, room_id: str, narration: str, next_turn_type: str = "PLAYER", 
                         active_players: Optional[List[str]] = None, is_dice_turn: bool = False, 
                         difficulty: int = 10, action_desc: str = "测试检定") -> Dict[str, Any]:
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
            Dict[str, Any]: 模拟结果
        """
        data = {
            "room_id": room_id,
            "narration": narration,
            "next_turn_type": next_turn_type,
            "is_dice_turn": is_dice_turn
        }
        
        if active_players:
            data["active_players"] = active_players
        
        if is_dice_turn:
            data["difficulty"] = difficulty
            data["action_desc"] = action_desc
        
        return self._request("POST", "/api/debug/simulate_dm_turn", data)
