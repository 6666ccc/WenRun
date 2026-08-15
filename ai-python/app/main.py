from pathlib import Path

from dotenv import load_dotenv

# 必须在导入会读环境变量的模块之前加载（节点在 import 时就会创建 ChatOpenAI）
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from fastapi import FastAPI
from app.api.routes import chat

app = FastAPI(
    title="My API",
    version="0.1.0",
)

app.include_router(chat.router)


@app.get("/")
def root():
    return {"message": "Hello FastAPI"}
