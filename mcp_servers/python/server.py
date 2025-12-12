# python_mcp_server.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class PythonCode(BaseModel):
    code: str

@app.post("/execute_python")
async def execute_python(request: PythonCode):
    code = request.code
    
    # Simple security check (still needed to prevent immediate file/system access)
    if any(keyword in code for keyword in ['os.', 'sys.', 'open(', 'import ', 'while', 'def']):
        raise HTTPException(status_code=403, detail="Restricted keyword found. Only simple math and assignments are allowed.")

    try:
        local_scope = {}
        exec(code, {'__builtins__': None}, local_scope) 
        
        if 'result' in local_scope:
            return {"status": "success", "output": local_scope['result']}
        elif 'output' in local_scope:
            return {"status": "success", "output": local_scope['output']}
        else:
             return {"status": "success", "output": "Code executed but no explicit 'result' variable found."}

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Python Execution Error: {str(e)}")
