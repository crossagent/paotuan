import logging
from typing import List, Dict, Any, Optional, Union

from models.entities import TurnType, DiceTurn, ActionTurn
from utils.scenario_loader import ScenarioLoader

logger = logging.getLogger(__name__)

class NarrationService:
    """叙述服务，处理AI叙述相关的业务逻辑"""
    
    def __init__(self, ai_service, rule_engine):
        self.ai_service = ai_service
        self.rule_engine = rule_engine
        
    async def prepare_context(self, match, current_turn, players) -> dict:
        """准备AI叙述的上下文信息"""
        player_names = [p.name for p in players]
        player_ids = [p.id for p in players]
        
        previous_actions = ""
        dice_results = None
        
        # 获取上一个回合的玩家行动
        if len(match.turns) > 1:
            prev_turn = [t for t in match.turns if t.id != current_turn.id][-1]
            if prev_turn.turn_type == TurnType.PLAYER:
                if isinstance(prev_turn, DiceTurn):
                    # 如果上一回合是掷骰子回合，获取掷骰子结果
                    dice_results = self.rule_engine.process_dice_turn_results(prev_turn)
                elif isinstance(prev_turn, ActionTurn):
                    # 普通行动回合，获取玩家行动
                    actions = []
                    for pid, action in prev_turn.actions.items():
                        player_name = next((p.name for p in players if p.id == pid), pid)
                        actions.append(f"{player_name}: {action}")
                    previous_actions = "\n".join(actions)
        
        # 准备生成上下文
        return {
            "current_scene": match.scene,
            "players": ", ".join(player_names),
            "player_actions": previous_actions or "没有玩家行动",
            "history": "（历史记录将在这里添加）", # 实际实现需要保存历史记录
            "dice_results": dice_results,  # 添加掷骰子结果
            "player_ids": player_ids  # 添加玩家ID列表
        }
        
    async def load_scenario(self, match):
        """加载剧本（如果有）"""
        if not match.scenario_id:
            return None
            
        scenario_loader = ScenarioLoader()
        scenario = scenario_loader.load_scenario(match.scenario_id)
        
        if scenario:
            logger.info(f"加载剧本: {scenario.name}, 当前事件: {scenario.current_event_index + 1}/{len(scenario.events)}")
            
        return scenario
        
    async def process_ai_response(self, response, room, scenario) -> List[Dict[str, str]]:
        """处理AI响应，返回需要发送的消息列表"""
        messages = []
        
        # 处理位置更新
        if hasattr(response, 'location_updates') and response.location_updates:
            location_messages = await self._process_location_updates(response.location_updates, room.players, scenario)
            messages.extend(location_messages)
            
        # 处理物品更新
        if hasattr(response, 'item_updates') and response.item_updates:
            item_messages = await self._process_item_updates(response.item_updates, room.players, scenario)
            messages.extend(item_messages)
            
        # 处理剧情进度
        if hasattr(response, 'plot_progress') and response.plot_progress is not None and scenario:
            plot_messages = await self._process_plot_progress(response.plot_progress, scenario, [p.id for p in room.players])
            messages.extend(plot_messages)
        
        # 处理游戏结束状态
        if hasattr(response, 'game_over') and response.game_over and scenario:
            scenario.game_over = True
            scenario.game_result = response.game_result
            
            # 保存剧本状态
            scenario_loader = ScenarioLoader()
            scenario_loader.save_scenario(scenario)
            
            # 通知所有玩家游戏结束
            result_type = "胜利" if response.game_result == "victory" else "失败"
            game_over_message = f"【游戏结束 - {result_type}】\n\n{response.narration}"
            
            for player in room.players:
                messages.append({"recipient": player.id, "content": game_over_message})
                
            # 添加一个特殊的系统消息，通知调用者更新Match状态
            messages.append({
                "type": "system_notification",
                "action": "finish_match",
                "result": response.game_result
            })
        
        return messages
        
    async def _process_location_updates(self, location_updates, players, scenario) -> List[Dict[str, str]]:
        """处理位置更新"""
        messages = []
        
        for location_update in location_updates:
            player_id = location_update.player_id
            new_location = location_update.new_location
            
            # 更新玩家位置
            for player in players:
                if player.id == player_id:
                    player.location = new_location
                    logger.info(f"更新玩家位置: 玩家={player.name}({player_id}), 新位置={new_location}")
                    
                    # 如果有剧本，也更新剧本中的玩家位置
                    if scenario:
                        scenario.player_location = new_location
                        scenario_loader = ScenarioLoader()
                        scenario_loader.save_scenario(scenario)
                        logger.info(f"更新剧本中的玩家位置: 新位置={new_location}")
                    break
                    
        return messages
    
    async def _process_item_updates(self, item_updates, players, scenario) -> List[Dict[str, str]]:
        """处理物品更新"""
        messages = []
        
        for item_update in item_updates:
            player_id = item_update.player_id
            item = item_update.item
            action = item_update.action
            
            # 更新玩家物品
            for player in players:
                if player.id == player_id:
                    if action == "add" and item not in player.items:
                        player.items.append(item)
                        logger.info(f"玩家获得物品: 玩家={player.name}({player_id}), 物品={item}")
                        
                        # 如果有剧本，也更新剧本中的已收集道具
                        if scenario and item not in scenario.collected_items:
                            scenario.collected_items.append(item)
                            scenario_loader = ScenarioLoader()
                            scenario_loader.save_scenario(scenario)
                            logger.info(f"更新剧本中的已收集道具: 添加物品={item}")
                    elif action == "remove" and item in player.items:
                        player.items.remove(item)
                        logger.info(f"玩家失去物品: 玩家={player.name}({player_id}), 物品={item}")
                        
                        # 如果有剧本，也更新剧本中的已收集道具
                        if scenario and item in scenario.collected_items:
                            scenario.collected_items.remove(item)
                            scenario_loader = ScenarioLoader()
                            scenario_loader.save_scenario(scenario)
                            logger.info(f"更新剧本中的已收集道具: 移除物品={item}")
                    break
                    
        return messages
        
    async def _process_plot_progress(self, plot_progress, scenario, player_ids) -> List[Dict[str, str]]:
        """处理剧情进度更新"""
        messages = []
        
        if plot_progress > scenario.current_event_index:
            old_event_index = scenario.current_event_index
            scenario.current_event_index = min(plot_progress, len(scenario.events) - 1)
            scenario_loader = ScenarioLoader()
            scenario_loader.save_scenario(scenario)
            logger.info(f"更新剧情进度: 从事件 {old_event_index + 1} 到 {scenario.current_event_index + 1}")
            
            # 通知所有玩家剧情进展
            if scenario.current_event_index < len(scenario.events):
                progress_message = f"【剧情进展】\n{scenario.events[scenario.current_event_index].content}"
                for pid in player_ids:
                    messages.append({"recipient": pid, "content": progress_message})
                
        return messages
