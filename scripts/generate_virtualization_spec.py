import os
import json

issue_key = os.environ["ISSUE_KEY"]

issue_file = f"output/{issue_key}/jira-issue.json"
spec_file = f"output/{issue_key}/virtualization-spec.json"

with open(issue_file, "r", encoding="utf-8") as f:
    issue = json.load(f)

fields = issue.get("fields", {})

service_name = fields.get("customfield_10178")
virtual_path = fields.get("customfield_10179")
request_content = fields.get("customfield_10180")
response_content = fields.get("customfield_10181")
real_endpoint = fields.get("customfield_10038")
service_definition = fields.get("customfield_10040")
method = fields.get("customfield_10044")
environment = fields.get("customfield_10037")
application = fields.get("customfield_10041")
cell = fields.get("customfield_10043")
service_name_real = fields.get("customfield_10045")

required_fields = {
    "Nombre de Servicio Virtual": service_name,
    "Path de virtualización": virtual_path,
    "Request de virtualización": request_content,
    "Response de virtualización": response_content,
    "Definición de Servicio": service_definition
}

missing = []

for field_name, value in required_fields.items():
    if value is None or str(value).strip() == "":
        missing.append(field_name)

if missing:
    raise ValueError(
        f"Campos obligatorios faltantes en Jira: {', '.join(missing)}"
    )

try:
    request_json = json.loads(request_content)
except Exception:
    raise ValueError("Request de virtualización no contiene JSON válido")

try:
    response_json = json.loads(response_content)
except Exception:
    raise ValueError("Response de virtualización no contiene JSON válido")

spec = {
    "issueKey": issue_key,
    "serviceName": service_name,
    "protocol": service_definition,
    "method": method,
    "environment": environment,
    "application": application,
    "requestingCell": cell,
    "realServiceName": service_name_real,
    "realEndpoint": real_endpoint,
    "virtualPath": f"/{virtual_path}",
    "port": 9080,
    "cases": [
        {
            "name": "Caso Principal",
            "statusCode": 200,
            "request": request_json,
            "response": response_json
        }
    ]
}

os.makedirs(f"output/{issue_key}", exist_ok=True)

with open(spec_file, "w", encoding="utf-8") as f:
    json.dump(spec, f, ensure_ascii=False, indent=2)

print("Virtualization spec generated successfully")
print(json.dumps(spec, ensure_ascii=False, indent=2))
