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
    "fields": "summary,description,status,issuetype,project,attachment,comment"
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

os.makedirs(f"output/{issue_key}", exist_ok=True)

with open(f"output/{issue_key}/jira-issue.json", "w", encoding="utf-8") as f:
    json.dump(issue, f, ensure_ascii=False, indent=2)

print(f"Jira issue fetched successfully: {issue_key}")
print(f"Summary: {issue['fields'].get('summary')}")
print(f"Status: {issue['fields'].get('status', {}).get('name')}")
