# fetch_mcp_server.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx # Required dependency for async HTTP requests

app = FastAPI()

class FetchRequest(BaseModel):
    url: str
    params: dict = {}
    timeout: float = 30.0

@app.post("/fetch_url")
async def fetch_url(request: FetchRequest):
    # Sanity Check to prevent internal network access
    if "localhost" in request.url or "127.0.0.1" in request.url:
        raise HTTPException(status_code=403, detail="Access to local network resources is forbidden.")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                request.url,
                params=request.params,
                timeout=request.timeout
            )
            response.raise_for_status() 
            
            return {
                "status": "success",
                "url": request.url,
                "status_code": response.status_code,
                "content_type": response.headers.get('Content-Type'),
                "content": response.text[:2000] # Truncate content
            }
        
        except httpx.TimeoutException:
            raise HTTPException(status_code=408, detail="External fetch request timed out.")
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"External request error: {type(e).__name__}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Unexpected error during fetch: {str(e)}")