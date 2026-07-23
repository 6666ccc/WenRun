from fastapi import FastAPI
from app.router import chat

app = FastAPI(
    title="My API",
    version="0.1.0"
)

app.include_router(chat.router)


@app.get("/")
def root():
    return {"message": "Hello FastAPI"}