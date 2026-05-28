#!/usr/bin/env python3
import os
import json
from datetime import datetime

import requests


CONFLUENCE_BASE_URL = os.environ["CONFLUENCE_BASE_URL"].rstrip("/")
CONFLUENCE_USER = os.environ["CONFLUENCE_USER"]
CONFLUENCE_API_TOKEN = os.environ["CONFLUENCE_API_TOKEN"]
CONFLUENCE_SPACE = os.environ["CONFLUENCE_SPACE"]
CONFLUENCE_PARENT_ID = os.environ["CONFLUENCE_PARENT_ID"]
ISSUE_KEY = os.environ["ISSUE_KEY"]

auth = (CONFLUENCE_USER, CONFLUENCE_API_TOKEN)


def sanear_cdata(texto: str) -> str:
    return texto.replace("]]>", "]]]]><![CDATA[>")


def content_to_string(value):
    if isinstance(value, str):
        return value

    return json.dumps(value, ensure_ascii=False, indent=2)


def extract_virtual_url(mcp_response: str, spec: dict, payload: dict) -> str:
    """
    Extrae la URL virtual directamente desde la respuesta del MCP.
    Busca cualquier valor que venga como http:// o https://.
    Prioriza URLs que usen el puerto 9080.
    """

    try:
        data = json.loads(mcp_response)

        candidates = []

        def walk(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if isinstance(value, str):
                        value_clean = value.strip()

                        if (
                            value_clean.startswith("http://")
                            or value_clean.startswith("https://")
                        ):
                            candidates.append(value_clean)

                    elif isinstance(value, (dict, list)):
                        walk(value)

            elif isinstance(obj, list):
                for item in obj:
                    walk(item)

        walk(data)

        for url in candidates:
            if ":9080" in url:
                return url

        if candidates:
            return candidates[0]

    except Exception as e:
        print(f"[WARN] No se pudo parsear mcp-response.json como JSON: {e}")

    fallback_url = (
        payload.get("urlVirtual")
        or payload.get("virtualUrl")
        or spec.get("urlVirtual")
        or spec.get("virtualUrl")
        or ""
    )

    return fallback_url


def generar_html(spec: dict, payload: dict, mcp_response: str) -> str:
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    service_name = spec.get("serviceName", ISSUE_KEY)
    virtual_path = spec.get("virtualPath", "")
    method = spec.get("method", "N/A")
    cases = spec.get("cases", [])

    virtual_url = extract_virtual_url(mcp_response, spec, payload)

    if not virtual_url:
        raise ValueError("No se pudo obtener la URL virtual desde la respuesta del MCP.")

    html = ""

    html += f"<h1>Documentación del Servicio Virtualizado — {service_name}</h1>\n"
    html += f"<p>Generada automáticamente el {ahora}</p>\n"

    html += "<h2>Información General</h2>\n<ul>\n"
    html += f"<li><b>Issue Jira:</b> {ISSUE_KEY}</li>\n"
    html += f"<li><b>Nombre del servicio:</b> {service_name}</li>\n"
    html += f"<li><b>Virtual Path:</b> {virtual_path}</li>\n"
    html += f"<li><b>Puerto:</b> {payload.get('port', 9080)}</li>\n"
    html += f"<li><b>URL Virtual:</b> {virtual_url}</li>\n"
    html += f"<li><b>Método:</b> {method}</li>\n"
    html += f"<li><b>Herramienta:</b> Parasoft SOAtest / Virtualize MCP</li>\n"
    html += "</ul>\n"

    html += "<h2>Payload enviado al MCP</h2>\n"
    payload_json = sanear_cdata(json.dumps(payload, ensure_ascii=False, indent=2))

    html += (
        '<ac:structured-macro ac:name="expand">\n'
        '  <ac:parameter ac:name="title">MCP Payload</ac:parameter>\n'
        '  <ac:rich-text-body>\n'
        '    <ac:structured-macro ac:name="code">\n'
        '      <ac:parameter ac:name="language">json</ac:parameter>\n'
        f'      <ac:plain-text-body><![CDATA[{payload_json}]]></ac:plain-text-body>\n'
        '    </ac:structured-macro>\n'
        '  </ac:rich-text-body>\n'
        '</ac:structured-macro>\n'
    )

    html += "<h2>Casos Virtualizados</h2>\n"

    for idx, case in enumerate(cases, start=1):
        case_name = (
            case.get("name")
            or case.get("nombre")
            or f"CP{idx:02d}"
        )

        request_content = sanear_cdata(content_to_string(case.get("request", {})))
        response_content = sanear_cdata(content_to_string(case.get("response", {})))

        html += f"<h3>{case_name}</h3>\n"

        html += (
            '<ac:structured-macro ac:name="expand">\n'
            '  <ac:parameter ac:name="title">Request</ac:parameter>\n'
            '  <ac:rich-text-body>\n'
            '    <ac:structured-macro ac:name="code">\n'
            '      <ac:parameter ac:name="language">json</ac:parameter>\n'
            f'      <ac:plain-text-body><![CDATA[{request_content}]]></ac:plain-text-body>\n'
            '    </ac:structured-macro>\n'
            '  </ac:rich-text-body>\n'
            '</ac:structured-macro>\n'
        )

        html += (
            '<ac:structured-macro ac:name="expand">\n'
            '  <ac:parameter ac:name="title">Response</ac:parameter>\n'
            '  <ac:rich-text-body>\n'
            '    <ac:structured-macro ac:name="code">\n'
            '      <ac:parameter ac:name="language">json</ac:parameter>\n'
            f'      <ac:plain-text-body><![CDATA[{response_content}]]></ac:plain-text-body>\n'
            '    </ac:structured-macro>\n'
            '  </ac:rich-text-body>\n'
            '</ac:structured-macro>\n'
        )

    html += "<h2>Respuesta MCP</h2>\n"
    response_clean = sanear_cdata(mcp_response or "Sin respuesta MCP disponible.")

    html += (
        '<ac:structured-macro ac:name="expand">\n'
        '  <ac:parameter ac:name="title">MCP Response</ac:parameter>\n'
        '  <ac:rich-text-body>\n'
        '    <ac:structured-macro ac:name="code">\n'
        '      <ac:parameter ac:name="language">json</ac:parameter>\n'
        f'      <ac:plain-text-body><![CDATA[{response_clean}]]></ac:plain-text-body>\n'
        '    </ac:structured-macro>\n'
        '  </ac:rich-text-body>\n'
        '</ac:structured-macro>\n'
    )

    return html


def buscar_pagina(title: str):
    url = f"{CONFLUENCE_BASE_URL}/wiki/rest/api/content"

    params = {
        "title": title,
        "spaceKey": CONFLUENCE_SPACE,
        "expand": "version"
    }

    response = requests.get(url, auth=auth, params=params)
    response.raise_for_status()

    results = response.json().get("results", [])

    if results:
        return results[0]

    return None


def limpiar_restricciones(page_id: str):
    url = f"{CONFLUENCE_BASE_URL}/wiki/rest/api/content/{page_id}/restriction"

    response = requests.delete(url, auth=auth)

    if response.status_code in (200, 204):
        print(f"[INFO] Restricciones eliminadas en página {page_id}")
    else:
        print(
            "[WARN] No se pudieron eliminar restricciones: "
            f"{response.status_code} - {response.text[:300]}"
        )


def publicar_confluence(title: str, html: str):
    headers = {
        "Content-Type": "application/json"
    }

    existing_page = buscar_pagina(title)

    if existing_page:
        page_id = existing_page["id"]
        current_version = existing_page["version"]["number"]

        url = f"{CONFLUENCE_BASE_URL}/wiki/rest/api/content/{page_id}"

        data = {
            "id": page_id,
            "type": "page",
            "title": title,
            "space": {
                "key": CONFLUENCE_SPACE
            },
            "ancestors": [
                {
                    "id": CONFLUENCE_PARENT_ID
                }
            ],
            "version": {
                "number": current_version + 1
            },
            "body": {
                "storage": {
                    "value": html,
                    "representation": "storage"
                }
            }
        }

        response = requests.put(
            url,
            auth=auth,
            headers=headers,
            json=data,
            timeout=120
        )

        response.raise_for_status()

        print(f"[INFO] Página actualizada en Confluence: {title}")
        limpiar_restricciones(page_id)

    else:
        url = f"{CONFLUENCE_BASE_URL}/wiki/rest/api/content"

        data = {
            "type": "page",
            "title": title,
            "space": {
                "key": CONFLUENCE_SPACE
            },
            "ancestors": [
                {
                    "id": CONFLUENCE_PARENT_ID
                }
            ],
            "body": {
                "storage": {
                    "value": html,
                    "representation": "storage"
                }
            }
        }

        response = requests.post(
            url,
            auth=auth,
            headers=headers,
            json=data,
            timeout=120
        )

        response.raise_for_status()

        page_id = response.json()["id"]

        print(f"[INFO] Página creada en Confluence: {title}")
        limpiar_restricciones(page_id)


def main():
    base_output = f"output/{ISSUE_KEY}"

    spec_path = f"{base_output}/virtualization-spec.json"
    payload_path = f"{base_output}/mcp-payload.json"
    response_path = f"{base_output}/mcp-response.json"
    html_path = f"{base_output}/confluence-documentation.html"

    if not os.path.exists(spec_path):
        raise FileNotFoundError(f"No existe el archivo {spec_path}")

    if not os.path.exists(payload_path):
        raise FileNotFoundError(f"No existe el archivo {payload_path}")

    with open(spec_path, "r", encoding="utf-8") as f:
        spec = json.load(f)

    with open(payload_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    mcp_response = ""

    if os.path.exists(response_path):
        with open(response_path, "r", encoding="utf-8") as f:
            mcp_response = f.read()
    else:
        print(f"[WARN] No existe {response_path}. Se continuará sin respuesta MCP.")

    service_name = spec.get("serviceName", ISSUE_KEY)

    title = f"Documentación Virtualización - {ISSUE_KEY} - {service_name}"

    html = generar_html(spec, payload, mcp_response)

    os.makedirs(base_output, exist_ok=True)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[INFO] HTML generado localmente: {html_path}")

    publicar_confluence(title, html)


if __name__ == "__main__":
    main()
