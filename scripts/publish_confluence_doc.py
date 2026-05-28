#!/usr/bin/env python3
import os
import json
import html
from datetime import datetime

import requests


CONFLUENCE_BASE_URL = os.environ["CONFLUENCE_BASE_URL"].rstrip("/")
CONFLUENCE_USER = os.environ["CONFLUENCE_USER"]
CONFLUENCE_API_TOKEN = os.environ["CONFLUENCE_API_TOKEN"]
CONFLUENCE_SPACE = os.environ["CONFLUENCE_SPACE"]
CONFLUENCE_PARENT_ID = os.environ["CONFLUENCE_PARENT_ID"]
ISSUE_KEY = os.environ["ISSUE_KEY"]

auth = (CONFLUENCE_USER, CONFLUENCE_API_TOKEN)


def esc(value) -> str:
    if value is None:
        return ""

    return html.escape(str(value), quote=True)


def sanear_cdata(texto: str) -> str:
    if texto is None:
        return ""

    return str(texto).replace("]]>", "]]]]><![CDATA[>")


def content_to_string(value):
    if value is None:
        return ""

    if isinstance(value, str):
        return value

    return json.dumps(value, ensure_ascii=False, indent=2)


def extract_virtual_url(mcp_response: str, spec: dict, payload: dict) -> str:
    try:
        data = json.loads(mcp_response)

        candidates = []

        def walk(obj):
            if isinstance(obj, dict):
                for _, value in obj.items():
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

    return (
        payload.get("urlVirtual")
        or payload.get("virtualUrl")
        or spec.get("urlVirtual")
        or spec.get("virtualUrl")
        or ""
    )


def code_block(title: str, content: str, language: str = "json") -> str:
    safe_content = sanear_cdata(content)

    return (
        '<ac:structured-macro ac:name="expand">\n'
        f'  <ac:parameter ac:name="title">{esc(title)}</ac:parameter>\n'
        '  <ac:rich-text-body>\n'
        '    <ac:structured-macro ac:name="code">\n'
        f'      <ac:parameter ac:name="language">{esc(language)}</ac:parameter>\n'
        f'      <ac:plain-text-body><![CDATA[{safe_content}]]></ac:plain-text-body>\n'
        '    </ac:structured-macro>\n'
        '  </ac:rich-text-body>\n'
        '</ac:structured-macro>\n'
    )


def generar_html(spec: dict, payload: dict, mcp_response: str) -> str:
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    service_name = spec.get("serviceName", ISSUE_KEY)
    virtual_path = spec.get("virtualPath", "")
    method = spec.get("method", "N/A")
    cases = spec.get("cases", [])

    virtual_url = extract_virtual_url(mcp_response, spec, payload)

    if not virtual_url:
        virtual_url = "No fue posible obtener la URL virtual desde la respuesta MCP."

    html_doc = ""

    html_doc += f"<h1>Documentación del Servicio Virtualizado — {esc(service_name)}</h1>\n"
    html_doc += f"<p>Generada automáticamente el {esc(ahora)}</p>\n"

    html_doc += "<h2>Información General</h2>\n<ul>\n"
    html_doc += f"<li><b>Issue Jira:</b> {esc(ISSUE_KEY)}</li>\n"
    html_doc += f"<li><b>Nombre del servicio:</b> {esc(service_name)}</li>\n"
    html_doc += f"<li><b>Virtual Path:</b> {esc(virtual_path)}</li>\n"
    html_doc += f"<li><b>Puerto:</b> {esc(payload.get('port', 9080))}</li>\n"
    html_doc += f"<li><b>URL Virtual:</b> {esc(virtual_url)}</li>\n"
    html_doc += f"<li><b>Método:</b> {esc(method)}</li>\n"
    html_doc += "<li><b>Herramienta:</b> Parasoft SOAtest / Virtualize MCP</li>\n"
    html_doc += "</ul>\n"

    payload_json = json.dumps(payload, ensure_ascii=False, indent=2)
    html_doc += "<h2>Payload enviado al MCP</h2>\n"
    html_doc += code_block("MCP Payload", payload_json, "json")

    html_doc += "<h2>Casos Virtualizados</h2>\n"

    for idx, case in enumerate(cases, start=1):
        case_name = (
            case.get("name")
            or case.get("nombre")
            or f"CP{idx:02d}"
        )

        request_content = content_to_string(case.get("request", {}))
        response_content = content_to_string(case.get("response", {}))

        html_doc += f"<h3>{esc(case_name)}</h3>\n"
        html_doc += code_block("Request", request_content, "json")
        html_doc += code_block("Response", response_content, "json")

    html_doc += "<h2>Respuesta MCP</h2>\n"
    html_doc += code_block(
        "MCP Response",
        mcp_response or "Sin respuesta MCP disponible.",
        "json"
    )

    return html_doc


def buscar_pagina(title: str):
    url = f"{CONFLUENCE_BASE_URL}/wiki/rest/api/content"

    params = {
        "title": title,
        "spaceKey": CONFLUENCE_SPACE,
        "expand": "version"
    }

    response = requests.get(
        url,
        auth=auth,
        params=params,
        timeout=120
    )

    print("SEARCH PAGE STATUS:", response.status_code)

    if response.status_code >= 400:
        print("SEARCH PAGE RESPONSE:")
        print(response.text)

    response.raise_for_status()

    results = response.json().get("results", [])

    if results:
        return results[0]

    return None


def limpiar_restricciones(page_id: str):
    url = f"{CONFLUENCE_BASE_URL}/wiki/rest/api/content/{page_id}/restriction"

    response = requests.delete(
        url,
        auth=auth,
        timeout=120
    )

    if response.status_code in (200, 204):
        print(f"[INFO] Restricciones eliminadas en página {page_id}")
    else:
        print(
            "[WARN] No se pudieron eliminar restricciones: "
            f"{response.status_code} - {response.text[:500]}"
        )


def publicar_confluence(title: str, html_doc: str):
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
                    "value": html_doc,
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

        print("UPDATE PAGE STATUS:", response.status_code)

        if response.status_code >= 400:
            print("UPDATE PAGE RESPONSE:")
            print(response.text)

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
                    "value": html_doc,
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

        print("CREATE PAGE STATUS:", response.status_code)

        if response.status_code >= 400:
            print("CREATE PAGE RESPONSE:")
            print(response.text)

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

    html_doc = generar_html(spec, payload, mcp_response)

    os.makedirs(base_output, exist_ok=True)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_doc)

    print(f"[INFO] HTML generado localmente: {html_path}")

    publicar_confluence(title, html_doc)


if __name__ == "__main__":
    main()
