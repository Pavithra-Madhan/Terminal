import requests

class MCP:
    servers = {
        "python": "http://localhost:8004",
        "fetch":  "http://localhost:8003",
        "fs":     "http://localhost:8002",
        "shell":  "http://localhost:8001",
    }

    @classmethod
    def call(cls, tool_call: dict):
        """
        Expected tool_call format:
        {
            "tool_call": "shell",
            "endpoint": "/exec",
            "payload": {"command": "ls -la"}
        }
        """
        name = tool_call["tool_call"]
        endpoint = tool_call.get("endpoint", "")
        payload = tool_call.get("payload", {})

        if name not in cls.servers:
            return {"error": f"Unknown MCP tool: {name}"}

        url = cls.servers[name] + endpoint

        try:
            r = requests.post(url, json=payload, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            return {"error": str(e)}
