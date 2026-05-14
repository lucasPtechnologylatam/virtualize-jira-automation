import os
import json
import requests

issue_key = os.environ["ISSUE_KEY"]
mcp_url = os.environ["SOATEST_MCP_URL"]
mcp_auth = os.environ["SOATEST_MCP_AUTH"]

spec_path = f"output/{issue_key}/virtualization-spec.json"
mcp_payload_path = f"output/{issue_key}/mcp-payload.json"

with open(spec_path, "r", encoding="utf-8") as f:
    spec = json.load(f)

case = spec["cases"][0]

request_content = json.dumps(
    case.get("request", {}),
    ensure_ascii=False,
    indent=2
)

response_content = json.dumps(
    case.get("response", {}),
    ensure_ascii=False,
    indent=2
)

mcp_arguments = {
    "action": "create",
    "name": spec["serviceName"],
    "deployment": spec["virtualPath"],
    "port": int(spec.get("port", 9080)),
    "requestContent": request_content,
    "responseContent": response_content
}

os.makedirs(f"output/{issue_key}", exist_ok=True)

with open(mcp_payload_path, "w", encoding="utf-8") as f:
    json.dump(mcp_arguments, f, ensure_ascii=False, indent=2)

headers = {
    "Authorization": mcp_auth,
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream"
}

# =========================
# MCP INITIALIZE
# =========================

initialize_payload = {
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

init_response = requests.post(
    mcp_url,
    headers=headers,
    json=initialize_payload,
    timeout=120
)

print("INITIALIZE STATUS:", init_response.status_code)
print("INITIALIZE HEADERS:", dict(init_response.headers))
print("INITIALIZE RESPONSE:", init_response.text)

init_response.raise_for_status()

session_id = init_response.headers.get("mcp-session-id")

if not session_id:
    raise RuntimeError("MCP session id not returned")

headers["mcp-session-id"] = session_id

# =========================
# TOOLS CALL
# =========================

tool_payload = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "mcp_soatest_manageVirtualServices",
        "arguments": mcp_arguments
    }
}

response = requests.post(
    mcp_url,
    headers=headers,
    json=tool_payload,
    timeout=120
)

print("MCP ARGUMENTS:")
print(json.dumps(mcp_arguments, ensure_ascii=False, indent=2))

print("TOOLS STATUS:", response.status_code)
print("TOOLS RESPONSE:", response.text)

response.raise_for_status()

print("Virtualization created successfully")
