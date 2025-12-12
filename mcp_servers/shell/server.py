# shell_mcp_server.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncio
import shlex
import subprocess

app = FastAPI()

class ShellCommand(BaseModel):
    command: str

MAX_TIMEOUT = 10.0 

@app.post("/execute_shell")
async def execute_shell(request: ShellCommand):
    command = request.command
    
    # NOTE: NO WHITELISTING - EXTREMELY DANGEROUS IN PRODUCTION
    try:
        # shlex.split is still used to correctly parse arguments
        command_parts = shlex.split(command)
        
        proc = await asyncio.create_subprocess_exec(
            *command_parts,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=MAX_TIMEOUT)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait() 
            raise HTTPException(status_code=408, detail=f"Command timed out after {MAX_TIMEOUT}s.")

        stdout_str = stdout.decode().strip()
        stderr_str = stderr.decode().strip()
        
        if proc.returncode != 0:
            return {"status": "error", "return_code": proc.returncode, "output": stderr_str}

        return {"status": "success", "return_code": 0, "output": stdout_str}

    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=f"Command not found on the system: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Shell Error: {str(e)}")
