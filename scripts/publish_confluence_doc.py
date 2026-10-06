#!/usr/bin/env python3

import os
import json
import html
import re
from datetime import datetime

import requests


# ============================================================
# VARIABLES CONFLUENCE
# ============================================================

CONFLUENCE_BASE_URL = os.environ["CONFLUENCE_BASE_URL"].rstrip("/")
CONFLUENCE_USER = os.environ["CONFLUENCE_USER"]
CONFLUENCE_API_TOKEN = os.environ["CONFLUENCE_API_TOKEN"]
CONFLUENCE_SPACE = os.environ["CONFLUENCE_SPACE"]
CONFLUENCE_PARENT_ID = os.environ["CONFLUENCE_PARENT_ID"]
ISSUE_KEY = os.environ["ISSUE_KEY"]


# ============================================================
# VARIABLES VIRTUALIZE
# ============================================================

VIRTUALIZE_HOST = os.getenv(
    "VIRTUALIZE_HOST",
    "soporte.laboratorytechnologylatam.com"
)

VIRTUALIZE_SCHEME = os.getenv(
    "VIRTUALIZE_SCHEME",
    "http"
)

VIRTUALIZE_PORT = int(
    os.getenv(
        "VIRTUALIZE_PORT",
        "9080"
    )
)


auth = (
    CONFLUENCE_USER,
    CONFLUENCE_API_TOKEN
)


# ============================================================
# UTILIDADES
# ============================================================

def esc(value) -> str:
    if value is None:
        return ""

    return html.escape(
        str(value),
        quote=True
    )


def sanear_cdata(texto: str) -> str:
    if texto is None:
        return ""

    return str(texto).replace(
        "]]>",
        "]]]]><![CDATA[>"
    )


def content_to_string(value):
    if value is None:
        return ""

    if isinstance(value, str):
        return value

    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2
    )


def normalize_virtual_path(path):
    """
    Virtual Path funcional.

    Ejemplo:
        enrolarUsuarios
        ->
        /enrolarUsuarios

    Este valor NO se utiliza para construir la URL
    del deployment.
    """

    if not path:
        return ""

    path = str(path).strip()

    if not path.startswith("/"):
        path = "/" + path

    return path


# ============================================================
# DEPLOYMENT REAL
# ============================================================

def extract_deployment_name(
    spec: dict,
    payload: dict,
    mcp_response: str
) -> str:
    """
    Obtiene el nombre real del deployment.

    Ejemplo:

        serviceName:
        RSEnrolamientoUsuarios

    Virtualize puede generar:

        RSEnrolamientoUsuarios
        RSEnrolamientoUsuarios_2
        RSEnrolamientoUsuarios_3

    Se busca primero en la respuesta MCP.

    IMPORTANTE:
    Nunca usamos virtualPath (/enrolarUsuarios)
    como nombre del deployment.
    """

    service_name = str(
        spec.get("serviceName")
        or payload.get("name")
        or ""
    ).strip()

    if not service_name:
        return ""

    if mcp_response:
        escaped_service = re.escape(service_name)

        # Busca:
        #
        # RSEnrolamientoUsuarios
        # RSEnrolamientoUsuarios_2
        # RSEnrolamientoUsuarios_3
        #
        pattern = rf"{escaped_service}(?:_\d+)?"

        matches = re.findall(
            pattern,
            mcp_response,
            flags=re.IGNORECASE
        )

        if matches:
            # Eliminar duplicados conservando orden
            unique_matches = []

            for match in matches:
                if match not in unique_matches:
                    unique_matches.append(match)

            print(
                "[INFO] Deployments encontrados "
                "en respuesta MCP:"
            )

            for match in unique_matches:
                print(
                    f"[INFO]   - {match}"
                )

            # ------------------------------------------------
            # PRIORIDAD:
            #
            # Preferimos los deployments que contienen sufijo.
            #
            # Ej:
            #
            # RSEnrolamientoUsuarios_3
            #
            # sobre:
            #
            # RSEnrolamientoUsuarios
            #
            # ------------------------------------------------

            with_suffix = []

            suffix_pattern = re.compile(
                rf"^{escaped_service}_(\d+)$",
                re.IGNORECASE
            )

            for match in unique_matches:
                suffix_match = suffix_pattern.match(
                    match
                )

                if suffix_match:
                    with_suffix.append(
                        (
                            int(
                                suffix_match.group(1)
                            ),
                            match
                        )
                    )

            if with_suffix:
                # Si existen varios:
                #
                # _2
                # _3
                #
                # tomamos el número mayor.
                with_suffix.sort(
                    key=lambda item: item[0],
                    reverse=True
                )

                deployment = with_suffix[0][1]

                print(
                    "[INFO] Deployment real seleccionado "
                    f"desde MCP: {deployment}"
                )

                return deployment

            # Si MCP solamente menciona el nombre base
            deployment = unique_matches[0]

            print(
                "[INFO] MCP solamente informó el "
                f"deployment base: {deployment}"
            )

            return deployment

    # ========================================================
    # FALLBACK 1
    #
    # Algunos payloads pueden contener explícitamente el
    # deployment real.
    # ========================================================

    deployment = payload.get(
        "realDeployment"
    )

    if deployment:
        deployment = str(
            deployment
        ).strip().strip("/")

        print(
            "[INFO] Deployment obtenido desde "
            f"payload.realDeployment: {deployment}"
        )

        return deployment


    deployment = payload.get(
        "deploymentName"
    )

    if deployment:
        deployment = str(
            deployment
        ).strip().strip("/")

        print(
            "[INFO] Deployment obtenido desde "
            f"payload.deploymentName: {deployment}"
        )

        return deployment


    # ========================================================
    # FALLBACK FINAL
    #
    # Usamos serviceName.
    #
    # IMPORTANTE:
    # NO usamos payload["deployment"] porque actualmente
    # puede contener /enrolarUsuarios.
    # ========================================================

    print(
        "[WARN] No fue posible detectar un deployment "
        "con sufijo desde la respuesta MCP."
    )

    print(
        "[WARN] Se utilizará serviceName como fallback: "
        f"{service_name}"
    )

    return service_name


# ============================================================
# URL VIRTUAL
# ============================================================

def build_virtual_url(
    spec: dict,
    payload: dict,
    mcp_response: str
) -> str:
    """
    Construye la URL de invocación utilizando el nombre
    REAL del deployment.

    Ejemplo:

        Deployment:
        RSEnrolamientoUsuarios_3

        URL:

        http://soporte.laboratorytechnologylatam.com:
        9080/RSEnrolamientoUsuarios_3
    """

    deployment_name = extract_deployment_name(
        spec,
        payload,
        mcp_response
    )

    if not deployment_name:
        return ""

    deployment_name = (
        str(deployment_name)
        .strip()
        .strip("/")
    )

    return (
        f"{VIRTUALIZE_SCHEME}://"
        f"{VIRTUALIZE_HOST}:"
        f"{VIRTUALIZE_PORT}/"
        f"{deployment_name}"
    )


# ============================================================
# MÉTODO HTTP
# ============================================================

VALID_HTTP_METHODS = {
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "HEAD",
    "OPTIONS"
}


def extract_http_method(
    spec: dict,
    mcp_response: str
) -> str:
    """
    Obtiene método HTTP.

    Prioridad:

    1. httpMethod
    2. requestMethod
    3. verb
    4. method si realmente contiene POST/GET/etc.
    5. respuesta MCP
    """

    possible_keys = [
        "httpMethod",
        "requestMethod",
        "verb",
        "method"
    ]

    for key in possible_keys:

        value = spec.get(key)

        if not value:
            continue

        method = str(
            value
        ).strip().upper()

        if method in VALID_HTTP_METHODS:
            return method


    # ========================================================
    # BUSCAR EN RESPUESTA MCP
    # ========================================================

    if mcp_response:

        pattern = (
            r"\b"
            r"(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)"
            r"\s+https?://"
        )

        match = re.search(
            pattern,
            mcp_response,
            re.IGNORECASE
        )

        if match:
            return (
                match
                .group(1)
                .upper()
            )

    return "N/A"


# ============================================================
# BLOQUES DE CÓDIGO CONFLUENCE
# ============================================================

def code_block(
    title: str,
    content: str,
    language: str = "json"
) -> str:

    safe_content = sanear_cdata(
        content
    )

    return (
        '<ac:structured-macro ac:name="expand">\n'
        f'  <ac:parameter ac:name="title">'
        f'{esc(title)}'
        f'</ac:parameter>\n'
        '  <ac:rich-text-body>\n'
        '    <ac:structured-macro ac:name="code">\n'
        f'      <ac:parameter ac:name="language">'
        f'{esc(language)}'
        f'</ac:parameter>\n'
        '      <ac:plain-text-body>'
        f'<![CDATA[{safe_content}]]>'
        '</ac:plain-text-body>\n'
        '    </ac:structured-macro>\n'
        '  </ac:rich-text-body>\n'
        '</ac:structured-macro>\n'
    )


# ============================================================
# GENERAR HTML
# ============================================================

def generar_html(
    spec: dict,
    payload: dict,
    mcp_response: str
) -> str:

    ahora = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    service_name = spec.get(
        "serviceName",
        ISSUE_KEY
    )

    # ========================================================
    # VIRTUAL PATH
    #
    # Sigue siendo /enrolarUsuarios.
    # Solamente es informativo/funcional.
    # ========================================================

    virtual_path = normalize_virtual_path(
        spec.get(
            "virtualPath",
            ""
        )
    )

    # ========================================================
    # DEPLOYMENT
    # ========================================================

    deployment_name = extract_deployment_name(
        spec,
        payload,
        mcp_response
    )

    # ========================================================
    # URL VIRTUAL REAL
    # ========================================================

    virtual_url = build_virtual_url(
        spec,
        payload,
        mcp_response
    )

    method = extract_http_method(
        spec,
        mcp_response
    )

    cases = spec.get(
        "cases",
        []
    )

    if not virtual_url:
        virtual_url = (
            "No fue posible determinar "
            "la URL virtual."
        )


    # ========================================================
    # HTML
    # ========================================================

    html_doc = ""

    html_doc += (
        f"<h1>"
        f"Documentación del Servicio Virtualizado — "
        f"{esc(service_name)}"
        f"</h1>\n"
    )

    html_doc += (
        f"<p>"
        f"Generada automáticamente el "
        f"{esc(ahora)}"
        f"</p>\n"
    )


    # ========================================================
    # INFORMACIÓN GENERAL
    # ========================================================

    html_doc += (
        "<h2>Información General</h2>\n"
        "<ul>\n"
    )

    html_doc += (
        f"<li>"
        f"<b>Issue Jira:</b> "
        f"{esc(ISSUE_KEY)}"
        f"</li>\n"
    )

    html_doc += (
        f"<li>"
        f"<b>Nombre del servicio:</b> "
        f"{esc(service_name)}"
        f"</li>\n"
    )

    html_doc += (
        f"<li>"
        f"<b>Virtual Path:</b> "
        f"{esc(virtual_path)}"
        f"</li>\n"
    )

    # ========================================================
    # NUEVO:
    # Mostrar deployment real
    # ========================================================

    html_doc += (
        f"<li>"
        f"<b>Deployment:</b> "
        f"{esc(deployment_name)}"
        f"</li>\n"
    )

    html_doc += (
        f"<li>"
        f"<b>Puerto:</b> "
        f"{esc(VIRTUALIZE_PORT)}"
        f"</li>\n"
    )


    # ========================================================
    # URL
    # ========================================================

    if (
        virtual_url.startswith("http://")
        or virtual_url.startswith("https://")
    ):

        html_doc += (
            f"<li>"
            f"<b>URL Virtual:</b> "
            f'<a href="{esc(virtual_url)}">'
            f"{esc(virtual_url)}"
            f"</a>"
            f"</li>\n"
        )

    else:

        html_doc += (
            f"<li>"
            f"<b>URL Virtual:</b> "
            f"{esc(virtual_url)}"
            f"</li>\n"
        )


    html_doc += (
        f"<li>"
        f"<b>Método HTTP:</b> "
        f"{esc(method)}"
        f"</li>\n"
    )

    html_doc += (
        "<li>"
        "<b>Herramienta:</b> "
        "Parasoft SOAtest / Virtualize MCP"
        "</li>\n"
    )

    html_doc += "</ul>\n"


    # ========================================================
    # PAYLOAD MCP
    # ========================================================

    payload_json = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2
    )

    html_doc += (
        "<h2>"
        "Payload enviado al MCP"
        "</h2>\n"
    )

    html_doc += code_block(
        "MCP Payload",
        payload_json,
        "json"
    )


    # ========================================================
    # CASOS VIRTUALIZADOS
    # ========================================================

    html_doc += (
        "<h2>"
        "Casos Virtualizados"
        "</h2>\n"
    )

    for idx, case in enumerate(
        cases,
        start=1
    ):

        case_name = (
            case.get("name")
            or case.get("nombre")
            or f"CP{idx:02d}"
        )

        request_content = content_to_string(
            case.get(
                "request",
                {}
            )
        )

        response_content = content_to_string(
            case.get(
                "response",
                {}
            )
        )

        html_doc += (
            f"<h3>"
            f"{esc(case_name)}"
            f"</h3>\n"
        )

        html_doc += code_block(
            "Request",
            request_content,
            "json"
        )

        html_doc += code_block(
            "Response",
            response_content,
            "json"
        )


    # ========================================================
    # RESPUESTA MCP
    # ========================================================

    html_doc += (
        "<h2>"
        "Respuesta MCP"
        "</h2>\n"
    )

    html_doc += code_block(
        "MCP Response",
        mcp_response
        or "Sin respuesta MCP disponible.",
        "json"
    )

    return html_doc


# ============================================================
# BUSCAR PÁGINA CONFLUENCE
# ============================================================

def buscar_pagina(title: str):

    url = (
        f"{CONFLUENCE_BASE_URL}"
        f"/wiki/rest/api/content"
    )

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

    print(
        "SEARCH PAGE STATUS:",
        response.status_code
    )

    if response.status_code >= 400:

        print(
            "SEARCH PAGE RESPONSE:"
        )

        print(
            response.text
        )

    response.raise_for_status()

    results = response.json().get(
        "results",
        []
    )

    if results:
        return results[0]

    return None


# ============================================================
# LIMPIAR RESTRICCIONES
# ============================================================

def limpiar_restricciones(
    page_id: str
):

    url = (
        f"{CONFLUENCE_BASE_URL}"
        f"/wiki/rest/api/content/"
        f"{page_id}/restriction"
    )

    response = requests.delete(
        url,
        auth=auth,
        timeout=120
    )

    if response.status_code in (
        200,
        204
    ):

        print(
            f"[INFO] Restricciones eliminadas "
            f"en página {page_id}"
        )

    else:

        print(
            "[WARN] No se pudieron eliminar "
            "restricciones: "
            f"{response.status_code} - "
            f"{response.text[:500]}"
        )


# ============================================================
# PUBLICAR CONFLUENCE
# ============================================================

def publicar_confluence(
    title: str,
    html_doc: str
):

    headers = {
        "Content-Type": "application/json"
    }

    existing_page = buscar_pagina(
        title
    )


    # ========================================================
    # ACTUALIZAR
    # ========================================================

    if existing_page:

        page_id = existing_page["id"]

        current_version = (
            existing_page[
                "version"
            ][
                "number"
            ]
        )

        url = (
            f"{CONFLUENCE_BASE_URL}"
            f"/wiki/rest/api/content/"
            f"{page_id}"
        )

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

        print(
            "UPDATE PAGE STATUS:",
            response.status_code
        )

        if response.status_code >= 400:

            print(
                "UPDATE PAGE RESPONSE:"
            )

            print(
                response.text
            )

        response.raise_for_status()

        print(
            f"[INFO] Página actualizada "
            f"en Confluence: {title}"
        )

        limpiar_restricciones(
            page_id
        )


    # ========================================================
    # CREAR
    # ========================================================

    else:

        url = (
            f"{CONFLUENCE_BASE_URL}"
            f"/wiki/rest/api/content"
        )

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

        print(
            "CREATE PAGE STATUS:",
            response.status_code
        )

        if response.status_code >= 400:

            print(
                "CREATE PAGE RESPONSE:"
            )

            print(
                response.text
            )

        response.raise_for_status()

        page_id = response.json()[
            "id"
        ]

        print(
            f"[INFO] Página creada "
            f"en Confluence: {title}"
        )

        limpiar_restricciones(
            page_id
        )


# ============================================================
# MAIN
# ============================================================

def main():

    base_output = (
        f"output/{ISSUE_KEY}"
    )

    spec_path = (
        f"{base_output}/"
        f"virtualization-spec.json"
    )

    payload_path = (
        f"{base_output}/"
        f"mcp-payload.json"
    )

    response_path = (
        f"{base_output}/"
        f"mcp-response.json"
    )

    html_path = (
        f"{base_output}/"
        f"confluence-documentation.html"
    )


    # ========================================================
    # VALIDAR ARCHIVOS
    # ========================================================

    if not os.path.exists(
        spec_path
    ):

        raise FileNotFoundError(
            f"No existe el archivo "
            f"{spec_path}"
        )


    if not os.path.exists(
        payload_path
    ):

        raise FileNotFoundError(
            f"No existe el archivo "
            f"{payload_path}"
        )


    # ========================================================
    # SPEC
    # ========================================================

    with open(
        spec_path,
        "r",
        encoding="utf-8"
    ) as f:

        spec = json.load(
            f
        )


    # ========================================================
    # PAYLOAD
    # ========================================================

    with open(
        payload_path,
        "r",
        encoding="utf-8"
    ) as f:

        payload = json.load(
            f
        )


    # ========================================================
    # MCP RESPONSE
    # ========================================================

    mcp_response = ""

    if os.path.exists(
        response_path
    ):

        with open(
            response_path,
            "r",
            encoding="utf-8"
        ) as f:

            mcp_response = f.read()

    else:

        print(
            f"[WARN] No existe "
            f"{response_path}. "
            "Se continuará sin "
            "respuesta MCP."
        )


    # ========================================================
    # DATOS
    # ========================================================

    service_name = spec.get(
        "serviceName",
        ISSUE_KEY
    )

    deployment_name = extract_deployment_name(
        spec,
        payload,
        mcp_response
    )

    virtual_url = build_virtual_url(
        spec,
        payload,
        mcp_response
    )

    method = extract_http_method(
        spec,
        mcp_response
    )


    title = (
        f"Documentación Virtualización - "
        f"{ISSUE_KEY} - "
        f"{service_name}"
    )


    # ========================================================
    # LOG
    # ========================================================

    print(
        "======================================"
    )

    print(
        "CONFLUENCE DOCUMENTATION"
    )

    print(
        "======================================"
    )

    print(
        f"Issue:       {ISSUE_KEY}"
    )

    print(
        f"Service:     {service_name}"
    )

    print(
        f"Deployment:  {deployment_name}"
    )

    print(
        f"Virtual URL: {virtual_url}"
    )

    print(
        f"HTTP Method: {method}"
    )


    # ========================================================
    # HTML
    # ========================================================

    html_doc = generar_html(
        spec,
        payload,
        mcp_response
    )


    # ========================================================
    # GUARDAR HTML
    # ========================================================

    os.makedirs(
        base_output,
        exist_ok=True
    )

    with open(
        html_path,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            html_doc
        )

    print(
        f"[INFO] HTML generado "
        f"localmente: {html_path}"
    )


    # ========================================================
    # PUBLICAR
    # ========================================================

    publicar_confluence(
        title,
        html_doc
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
