import os
import logging
import asyncio
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import uvicorn
from pathlib import Path
from web.routes import user_routes, room_routes, game_routes
from web.auth import auth_manager
from adapters.web_adapter import WebAdapter

# 配置日志
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="TRPG游戏服务器",
    description="TRPG游戏服务器Web API",
    version="1.0.0"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源，生产环境应限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局Web适配器
web_adapter = None

# 全局游戏实例
game_instance = None

# 异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"全局异常: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": f"服务器错误: {str(exc)}"}
    )

# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# 挂载API路由
app.include_router(user_routes.router)
app.include_router(room_routes.router)
app.include_router(game_routes.router)

# 静态文件服务
@app.get("/")
async def read_root():
    return FileResponse("static/web/index.html")

# 启动事件
@app.on_event("startup")
async def startup_event():
    logger.info("Web服务器启动")

# 关闭事件
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Web服务器关闭")
    if web_adapter:
        await web_adapter.stop()

def init_static_files():
    """初始化静态文件服务"""
    # 确保静态文件目录存在
    static_dir = Path("static/web")
    static_dir.mkdir(parents=True, exist_ok=True)
    
    # 挂载静态文件
    app.mount("/static", StaticFiles(directory="static"), name="static")

def init_web_adapter(game_server):
    """初始化Web适配器"""
    global web_adapter, game_instance
    
    # 创建Web适配器
    web_adapter = WebAdapter()
    
    # 注册到游戏服务器
    game_server.register_adapter(web_adapter)
    
    # 保存游戏实例引用
    game_instance = game_server.game_state
    
    # 设置路由模块的引用
    game_routes.set_web_adapter(web_adapter)
    room_routes.set_game_instance(game_instance)
    
    logger.info("Web适配器已初始化")
    return web_adapter

async def start_server(host="0.0.0.0", port=8000):
    """启动Web服务器"""
    init_static_files()
    
    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="info"
    )
    server = uvicorn.Server(config)
    
    logger.info(f"Web服务器启动于 http://{host}:{port}")
    await server.serve()

if __name__ == "__main__":
    # 直接运行此文件时的入口点
    # 注意：通常应该从main.py启动，这里仅用于开发测试
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
