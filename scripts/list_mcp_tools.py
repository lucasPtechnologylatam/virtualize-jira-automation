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

init_payload = {
    "jsonrpc": "2.0",
    "id": 0,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {
            "name": "github-actions-runner",
            "version": "1.0.0"
        }
    }
}

init_response = requests.post(mcp_url, headers=headers, json=init_payload, timeout=120)
init_response.raise_for_status()

session_id = init_response.headers.get("mcp-session-id")
headers["mcp-session-id"] = session_id

list_payload = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {}
}

response = requests.post(mcp_url, headers=headers, json=list_payload, timeout=120)

print("TOOLS LIST STATUS:", response.status_code)
print("TOOLS LIST RESPONSE:")
print(response.text)

response.raise_for_status()
