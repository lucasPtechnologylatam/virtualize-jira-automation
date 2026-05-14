import os
import json
import requests

mcp_url = os.environ["SOATEST_MCP_URL"]
mcp_auth = os.environ["SOATEST_MCP_AUTH"]

headers = {
    "Authorization": mcp_auth,
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream"
}

# 1. Initialize MCP session
init_payload = {
    "jsonrpc": "2.0",
    "id": 0,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {
            "roots": {
                "listChanged": True
            },
            "sampling": {}
        },
        "clientInfo": {
            "name": "Visual Studio Code",
            "version": "1.0.0"
        }
    }
}

init_response = requests.post(
    mcp_url,
    headers=headers,
    json=init_payload,
    timeout=120
)

print("INITIALIZE STATUS:", init_response.status_code)
print("INITIALIZE RESPONSE:")
print(init_response.text)

init_response.raise_for_status()

session_id = init_response.headers.get("mcp-session-id")

if not session_id:
    raise RuntimeError("MCP session id not returned")

headers["mcp-session-id"] = session_id

print("MCP SESSION ID:", session_id)

# 2. Notify initialized
initialized_payload = {
    "jsonrpc": "2.0",
    "method": "notifications/initialized",
    "params": {}
}

initialized_response = requests.post(
    mcp_url,
    headers=headers,
    json=initialized_payload,
    timeout=120
)

print("INITIALIZED STATUS:", initialized_response.status_code)
print("INITIALIZED RESPONSE:")
print(initialized_response.text)

initialized_response.raise_for_status()

# 3. List tools
list_payload = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {}
}

response = requests.post(
    mcp_url,
    headers=headers,
    json=list_payload,
    timeout=120
)

print("TOOLS LIST STATUS:", response.status_code)
print("TOOLS LIST RESPONSE:")
print(response.text)

response.raise_for_status()
