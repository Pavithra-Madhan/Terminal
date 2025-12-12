# sqlite_mcp_server.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
import os

app = FastAPI()

class SqlQuery(BaseModel):
    query: str

DB_PATH = os.environ.get("DB_PATH", "system/system_stm.sqlite")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row 
    return conn

@app.post("/execute_query")
async def execute_query(request: SqlQuery):
    query = request.query
    
    # Enforce Read-Only Access for safety, allowing any search query
    if not query.strip().upper().startswith("SELECT"):
        raise HTTPException(status_code=403, detail="Access denied. Only READ-ONLY (SELECT) queries are permitted.")
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(query)
        
        results = [dict(row) for row in cursor.fetchall()]
        return {"status": "success", "results": results, "row_count": len(results)}

    except sqlite3.Error as e:
        raise HTTPException(status_code=400, detail=f"SQLite Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
    finally:
        if conn:
            conn.close()