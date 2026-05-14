import os
import json
import requests

issue_key = os.environ["ISSUE_KEY"]
mcp_url = os.environ["SOATEST_MCP_URL"]
mcp_auth = os.environ["SOATEST_MCP_AUTH"]

spec_path = f"output/{issue_key}/virtualization-spec.json"

with open(spec_path, "r", encoding="utf-8") as f:
    spec = json.load(f)

case = spec["cases"][0]

request_content = json.dumps(case.get("request", {}), ensure_ascii=False, indent=2)
response_content = json.dumps(case.get("response", {}), ensure_ascii=False, indent=2)

mcp_arguments = {
    "action": "create",
    "name": spec["serviceName"],
    "deployment": spec["virtualPath"],
    "port": int(spec.get("port", 9080)),
    "requestContent": request_content,
    "responseContent": response_content
}

os.makedirs(f"output/{issue_key}", exist_ok=True)

with open(f"output/{issue_key}/mcp-payload.json", "w", encoding="utf-8") as f:
    json.dump(mcp_arguments, f, ensure_ascii=False, indent=2)

payload = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "mcp_soatest_manageVirtualServices",
        "arguments": mcp_arguments
    }
}

headers = {
    "Authorization": mcp_auth,
    "Content-Type": "application/json",
    "Accept": "application/json"
}

response = requests.post(
    mcp_url,
    headers=headers,
    json=payload,
    timeout=120
)

print("MCP payload:")
print(json.dumps(mcp_arguments, ensure_ascii=False, indent=2))

print("MCP status:", response.status_code)
print(response.text)

response.raise_for_status()
