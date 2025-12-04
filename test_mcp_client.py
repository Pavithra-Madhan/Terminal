import requests, json

def call_tool(port, tool, payload):
    url = f"http://localhost:{port}/call"
    body = {"tool": tool, "input": payload}
    r = requests.post(url, json=body, timeout=10)
    print(f"--- {tool} @ {port} ---")
    try:
        print(json.dumps(r.json(), indent=2) )
    except:
        print(r.text)

if __name__ == "__main__":
    # FS read/write test
    call_tool(8001, "write", {"path":"/tmp/mcp_test.txt","content":"hello from MCP"})
    call_tool(8001, "read", "/tmp/mcp_test.txt")

    # FETCH test
    call_tool(8002, "get", "https://httpbin.org/get")

    # PYTHON exec test
    call_tool(8003, "exec", "x = 2+2\n")

    # SHELL test
    call_tool(8004, "bash", "echo shell-run && ls -la /tmp | head -5")
