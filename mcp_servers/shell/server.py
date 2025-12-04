from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import subprocess
import requests
import os

app = FastAPI(title="${server} server")

class ToolRequest(BaseModel):
    name: str
    arguments: dict

@app.post("/call")
async def call_tool(request: ToolRequest):
    return {"result": "Tool ${server} is working!"}

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
