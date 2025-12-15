from fastapi import FastAPI, HTTPException
import sqlite3
import os
import logging

app = FastAPI()
logging.basicConfig(level=logging.INFO)

# SIMPLE but CLEAR database mapping
DB_PATHS = {
    "system": "/app/system.db",
    "memory": "/app/memory.db",
}

@app.post("/execute_query")
async def execute_query(request: dict):
    try:
        # 1. Validate input
        db_name = request.get("db_name", "system")
        query = request.get("query", "").strip()
        
        if not query:
            raise HTTPException(400, "Query cannot be empty")
        
        if db_name not in DB_PATHS:
            raise HTTPException(400, f"Unknown database: {db_name}. Use 'system' or 'memory'")
        
        # 2. Get database path
        db_path = DB_PATHS[db_name]
        
        # 3. Check file exists (better error than SQLite's vague one)
        if not os.path.exists(db_path):
            raise HTTPException(500, f"Database file missing: {db_path}")
        
        # 4. Execute with logging
        logging.info(f"Executing on {db_name}: {query[:50]}...")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(query)
        
        if query.upper().startswith("SELECT"):
            results = cursor.fetchall()
            return {
                "status": "success",
                "database": db_name,
                "results": results,
                "count": len(results)
            }
        else:
            conn.commit()
            return {"status": "executed", "database": db_name}
            
    except HTTPException:
        raise  # Re-raise our clear errors
    except sqlite3.Error as e:
        # CLEAR error with context
        raise HTTPException(400, f"Database error on '{db_name}': {str(e)}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(500, f"Server error: {type(e).__name__}")
    finally:
        if 'conn' in locals():
            conn.close()