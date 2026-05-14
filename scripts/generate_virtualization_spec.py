import os
import json

issue_key = os.environ["ISSUE_KEY"]
issue_file = f"output/{issue_key}/jira-issue.json"
spec_file = f"output/{issue_key}/virtualization-spec.json"

with open(issue_file, "r", encoding="utf-8") as f:
    issue = json.load(f)

fields = issue.get("fields", {})

summary = fields.get("summary", "")
description = fields.get("description", {})

spec = {
    "issueKey": issue_key,
    "serviceName": summary.replace(" ", ""),
    "protocol": "REST",
    "method": "POST",
    "realEndpoint": "",
    "virtualPath": f"/{summary.lower().replace(' ', '-')}",
    "cases": [
        {
            "name": "Caso exitoso",
            "statusCode": 200,
            "request": {},
            "response": {
                "codigo": "00",
                "mensaje": "Respuesta exitosa"
            }
        }
    ],
    "source": {
        "jiraSummary": summary,
        "jiraDescriptionRaw": description
    }
}

with open(spec_file, "w", encoding="utf-8") as f:
    json.dump(spec, f, ensure_ascii=False, indent=2)

print(f"Virtualization spec generated: {spec_file}")
