import os
import json
import requests
from requests.auth import HTTPBasicAuth

jira_base_url = os.environ["JIRA_BASE_URL"].rstrip("/")
jira_email = os.environ["JIRA_EMAIL"]
jira_api_token = os.environ["JIRA_API_TOKEN"]
issue_key = os.environ["ISSUE_KEY"]

url = f"{jira_base_url}/rest/api/3/issue/{issue_key}"

params = {
    "fields": "*all",
    "expand": "names,schema"
}

response = requests.get(
    url,
    params=params,
    auth=HTTPBasicAuth(jira_email, jira_api_token),
    headers={"Accept": "application/json"},
    timeout=30
)

if response.status_code != 200:
    print(f"Error calling Jira: {response.status_code}")
    print(response.text)
    response.raise_for_status()

issue = response.json()
fields = issue.get("fields", {})
names = issue.get("names", {})
schema = issue.get("schema", {})

output_dir = f"output/{issue_key}"
os.makedirs(output_dir, exist_ok=True)

with open(f"{output_dir}/jira-issue.json", "w", encoding="utf-8") as f:
    json.dump(issue, f, ensure_ascii=False, indent=2)

custom_fields_debug = {}

for field_id, value in fields.items():
    field_name = names.get(field_id, field_id)

    if field_id.startswith("customfield_"):
        custom_fields_debug[field_id] = {
            "name": field_name,
            "schema": schema.get(field_id),
            "value": value
        }

with open(f"{output_dir}/jira-custom-fields-debug.json", "w", encoding="utf-8") as f:
    json.dump(custom_fields_debug, f, ensure_ascii=False, indent=2)

readable_summary = {
    "issueKey": issue_key,
    "summary": fields.get("summary"),
    "issueType": fields.get("issuetype", {}).get("name"),
    "status": fields.get("status", {}).get("name"),
    "project": fields.get("project", {}).get("key"),
    "customFieldsCount": len(custom_fields_debug),
    "customFieldsFile": "jira-custom-fields-debug.json"
}

with open(f"{output_dir}/jira-readable-summary.json", "w", encoding="utf-8") as f:
    json.dump(readable_summary, f, ensure_ascii=False, indent=2)

print(f"Jira issue fetched successfully: {issue_key}")
print(f"Summary: {fields.get('summary')}")
print(f"Status: {fields.get('status', {}).get('name')}")
print(f"Custom fields detected: {len(custom_fields_debug)}")
print(f"Debug file generated: {output_dir}/jira-custom-fields-debug.json")
