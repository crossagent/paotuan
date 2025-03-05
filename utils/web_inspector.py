import json
import asyncio
import logging
from typing import Dict, Any
from aiohttp import web
from utils.inspector import GameStateInspector

logger = logging.getLogger("web_inspector")

class WebInspector:
    def __init__(self, state_inspector: GameStateInspector, host='0.0.0.0', port=54232):
        self.state_inspector = state_inspector
        self.host = host
        self.port = port
        self.app = web.Application()
        self.runner = None
        self._setup_routes()
        self._setup_cors()
        
    def _setup_routes(self):
        """设置路由"""
        self.app.add_routes([
            # API路由
            web.get('/api/state', self.handle_all_state),
            web.get('/api/state/{room_id}', self.handle_room_state),
            web.get('/api/state/{room_id}/match', self.handle_match_state),
            web.get('/api/state/{room_id}/turn', self.handle_turn_state),
            web.get('/api/state/{room_id}/players', self.handle_players_state),
            
            # 静态文件服务
            web.static('/inspector', 'static/inspector')
        ])
        
        # 设置主页重定向到前端页面
        self.app.router.add_get('/', self.redirect_to_inspector)
        
    def _setup_cors(self):
        """设置CORS"""
        # 允许跨域请求
        @web.middleware
        async def cors_middleware(request, handler):
            response = await handler(request)
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            return response
            
        self.app.middlewares.append(cors_middleware)
        
    async def redirect_to_inspector(self, request):
        """重定向到检查器页面"""
        return web.HTTPFound('/inspector/index.html')
        
    async def handle_all_state(self, request):
        """处理获取所有状态的请求"""
        result = self.state_inspector.dump_all_state()
        return web.json_response(result)
    
    async def handle_room_state(self, request):
        """处理获取房间状态的请求"""
        room_id = request.match_info.get('room_id')
        result = self.state_inspector.dump_room_state(room_id)
        return web.json_response(result)
    
    async def handle_match_state(self, request):
        """处理获取比赛状态的请求"""
        room_id = request.match_info.get('room_id')
        result = self.state_inspector.dump_match_state(room_id)
        return web.json_response(result)
    
    async def handle_turn_state(self, request):
        """处理获取回合状态的请求"""
        room_id = request.match_info.get('room_id')
        result = self.state_inspector.dump_current_turn(room_id)
        return web.json_response(result)
    
    async def handle_players_state(self, request):
        """处理获取玩家状态的请求"""
        room_id = request.match_info.get('room_id')
        result = self.state_inspector.dump_players(room_id)
        return web.json_response(result)
    
    async def start(self):
        """启动Web服务器"""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, self.host, self.port)
        await site.start()
        logger.info(f"状态检查器Web服务已启动 http://{self.host}:{self.port}")
    
    async def stop(self):
        """停止Web服务器"""
        if self.runner:
            await self.runner.cleanup()
            logger.info("状态检查器Web服务已停止")
