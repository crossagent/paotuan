import logging
from typing import List, Dict, Any, Optional, Union

from adapters.base import GameEvent, ListScenariosEvent, GetScenarioEvent
from services.commands.base import GameCommand
from utils.scenario_loader import ScenarioLoader

logger = logging.getLogger(__name__)

class ListScenariosCommand(GameCommand):
    """处理获取剧本列表事件的命令"""
    
    async def execute(self, event: ListScenariosEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        """执行命令
        
        Args:
            event: ListScenariosEvent - 事件对象
            
        Returns:
            List[Union[GameEvent, Dict[str, str]]]: 响应消息列表
        """
        player_id = event.data["player_id"]
        
        logger.info(f"处理获取剧本列表事件: 玩家ID={player_id}")
        
        try:
            # 加载剧本
            scenario_loader = ScenarioLoader()
            scenarios = scenario_loader.list_scenarios()
            
            return [{"recipient": player_id, "content": scenarios, "type": "scenarios_list"}]
        except Exception as e:
            logger.error(f"获取剧本列表失败: {str(e)}")
            return [{"recipient": player_id, "content": f"获取剧本列表失败: {str(e)}"}]


class GetScenarioCommand(GameCommand):
    """处理获取剧本详情事件的命令"""
    
    async def execute(self, event: GetScenarioEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        """执行命令
        
        Args:
            event: GetScenarioEvent - 事件对象
            
        Returns:
            List[Union[GameEvent, Dict[str, str]]]: 响应消息列表
        """
        player_id = event.data["player_id"]
        scenario_id = event.data["scenario_id"]
        
        logger.info(f"处理获取剧本详情事件: 玩家ID={player_id}, 剧本ID={scenario_id}")
        
        try:
            # 加载剧本
            scenario_loader = ScenarioLoader()
            scenario = scenario_loader.load_scenario(scenario_id)
            
            if not scenario:
                return [{"recipient": player_id, "content": f"剧本不存在: {scenario_id}"}]
            
            # 构建场景列表
            scenes = []
            for scene in scenario.scenes:
                scenes.append({
                    "name": scene.name,
                    "description": scene.description
                })
            
            scenario_info = {
                "id": scenario_id,
                "name": scenario.name,
                "description": scenario.description,
                "player_count": scenario.player_count,
                "main_scene": scenario.main_scene,
                "scenes": scenes
            }
            
            return [{"recipient": player_id, "content": scenario_info, "type": "scenario_detail"}]
        except Exception as e:
            logger.error(f"获取剧本详情失败: {str(e)}")
            return [{"recipient": player_id, "content": f"获取剧本详情失败: {str(e)}"}]
