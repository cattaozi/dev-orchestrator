import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"
)
load_dotenv(env_path)

BACKEND_HOST = os.getenv("BACKEND_HOST", "0.0.0.0")

try:
    BACKEND_PORT = int(os.getenv("BACKEND_PORT", "17000"))
except ValueError:
    BACKEND_PORT = 17000

from loguru import logger
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Create logs directory - 使用项目目录下的 logs 文件夹
logs_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs"
)
os.makedirs(logs_dir, exist_ok=True)


# Configure logging
def setup_logging():
    """配置日志：同时输出到控制台和文件"""
    # 移除 loguru 默认的 handler
    logger.remove()

    # 日志格式
    log_format = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}"
    )

    # 控制台输出
    logger.add(
        sys.stdout,
        format=log_format,
        level="INFO",
        colorize=True,
    )

    # 文件输出
    logger.add(
        os.path.join(logs_dir, "app.log"),
        format=log_format,
        level="DEBUG",
        rotation="100 MB",
        retention="7 days",
        compression="gz",
        encoding="utf-8",
    )

    # 配置默认的 trace_id
    logger.configure(extra={"trace_id": "-"})

    # 拦截标准库 logging
    class InterceptHandler(logging.Handler):
        def emit(self, record):
            level = (
                logger.level(record.levelname).name
                if record.levelname in logger._core.levels
                else record.levelno
            )
            logger.opt(depth=6, exception=record.exc_info).log(level, record.getMessage())

    logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO, force=True)


setup_logging()
logger.info("Logging initialized")

# Initialize database
from db import init_db

init_db()

# Import routers
from routers import projects, prds, issues, workers, sessions, config

app = FastAPI(title="DevOrchestrator API")


# Global exception handler - 兜底捕获所有未处理异常
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception on {request.method} {request.url.path}: {exc}")
    return JSONResponse(status_code=500, content={"detail": f"Internal server error: {str(exc)}"})


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"--> {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"<-- {request.method} {request.url.path} {response.status_code}")
    return response


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(projects.router)
app.include_router(prds.router)
app.include_router(issues.router)
app.include_router(workers.router)
app.include_router(sessions.router)
app.include_router(config.router)


@app.get("/")
def root():
    return {"message": "DevOrchestrator API"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=BACKEND_HOST, port=BACKEND_PORT)
