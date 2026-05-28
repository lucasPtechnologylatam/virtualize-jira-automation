import os
import json
import requests

issue_key = os.environ["ISSUE_KEY"]
mcp_url = os.environ["SOATEST_MCP_URL"]
mcp_auth = os.environ["SOATEST_MCP_AUTH"]

base_output = f"output/{issue_key}"

spec_path = f"{base_output}/virtualization-spec.json"
mcp_payload_path = f"{base_output}/mcp-payload.json"
mcp_response_path = f"{base_output}/mcp-response.json"

if not os.path.exists(spec_path):
    raise FileNotFoundError(f"No existe el archivo {spec_path}")

with open(spec_path, "r", encoding="utf-8") as f:
    spec = json.load(f)

cases = spec.get("cases", [])

if not cases:
    raise ValueError("No existen casos en virtualization-spec.json")

case = cases[0]


def content_to_string(value):
    if isinstance(value, str):
        return value

    return json.dumps(value, ensure_ascii=False, indent=2)


request_content = content_to_string(case.get("request"))
response_content = content_to_string(case.get("response"))

if not request_content or request_content == "{}":
    raise ValueError("requestContent vacío. No se enviará creación al MCP.")

if not response_content or response_content == "{}":
    raise ValueError("responseContent vacío. No se enviará creación al MCP.")


mcp_arguments = {
    "action": "create",
    "name": spec["serviceName"],
    "deployment": spec["virtualPath"],
    "port": 9080,
    "requestContent": request_content,
    "responseContent": response_content
}

os.makedirs(base_output, exist_ok=True)

with open(mcp_payload_path, "w", encoding="utf-8") as f:
    json.dump(mcp_arguments, f, ensure_ascii=False, indent=2)

headers = {
    "Authorization": mcp_auth,
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream"
}

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

print("======================================")
print("INITIALIZING MCP SESSION")
print("======================================")

init_response = requests.post(
    mcp_url,
    headers=headers,
    json=initialize_payload,
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

print("======================================")
print("CREATING VIRTUALIZATION")
print("======================================")

tool_payload = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "manageVirtualServices",
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
print("TOOLS RESPONSE:")
print(response.text)

with open(mcp_response_path, "w", encoding="utf-8") as f:
    f.write(response.text)

response.raise_for_status()

print("======================================")
print("VIRTUALIZATION CREATED SUCCESSFULLY")
print("======================================")
