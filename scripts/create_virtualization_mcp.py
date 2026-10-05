import os
import json
import re
import requests


# ============================================================
# VARIABLES DE ENTORNO
# ============================================================

issue_key = os.environ["ISSUE_KEY"]
mcp_url = os.environ["SOATEST_MCP_URL"]
mcp_auth = os.environ["SOATEST_MCP_AUTH"]

# Virtualize utiliza un listener compartido.
# Todas las virtualizaciones se despliegan en este puerto.
virtualize_port = int(os.getenv("VIRTUALIZE_PORT", "9080"))

# Solo se utiliza para mostrar/calcular información.
virtualize_host = os.getenv(
    "VIRTUALIZE_HOST",
    "soporte.laboratorytechnologylatam.com"
)

virtualize_scheme = os.getenv(
    "VIRTUALIZE_SCHEME",
    "http"
)


# ============================================================
# RUTAS
# ============================================================

base_output = f"output/{issue_key}"

spec_path = f"{base_output}/virtualization-spec.json"
mcp_payload_path = f"{base_output}/mcp-payload.json"
mcp_response_path = f"{base_output}/mcp-response.json"


# ============================================================
# FUNCIONES
# ============================================================

def content_to_string(value):
    """
    Convierte request/response a texto para enviarlo al MCP.
    """

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
    Garantiza que el Virtual Path comience con /.
    """

    if not path:
        return ""

    path = str(path).strip()

    if not path.startswith("/"):
        path = "/" + path

    return path


def build_virtual_url(host, port, virtual_path, scheme="http"):
    """
    Construye la URL REAL esperada de Virtualize.

    IMPORTANTE:
    No utilizamos la URL informada por el MCP porque actualmente
    el MCP puede indicar incorrectamente que el servicio utiliza
    9081 cuando Virtualize realmente lo despliega sobre 9080.
    """

    virtual_path = normalize_virtual_path(virtual_path)

    return f"{scheme}://{host}:{port}{virtual_path}"


def detect_reported_ports(text):
    """
    Busca URLs reportadas por el MCP únicamente para diagnóstico.
    No modifica el puerto real de despliegue.
    """

    if not text:
        return []

    pattern = r"https?://[^\s\"']+:(\d+)[^\s\"']*"

    return re.findall(pattern, text)


# ============================================================
# CARGAR SPEC
# ============================================================

if not os.path.exists(spec_path):
    raise FileNotFoundError(
        f"No existe el archivo {spec_path}"
    )


with open(spec_path, "r", encoding="utf-8") as f:
    spec = json.load(f)


# ============================================================
# VALIDACIONES
# ============================================================

service_name = spec.get("serviceName")

if not service_name:
    raise ValueError(
        "serviceName no existe en virtualization-spec.json"
    )


virtual_path = normalize_virtual_path(
    spec.get("virtualPath")
)

if not virtual_path:
    raise ValueError(
        "virtualPath no existe en virtualization-spec.json"
    )


cases = spec.get("cases", [])

if not cases:
    raise ValueError(
        "No existen casos en virtualization-spec.json"
    )


# Actualmente el MCP trabaja con el primer caso para crear
# la virtualización principal.
case = cases[0]


request_content = content_to_string(
    case.get("request")
)

response_content = content_to_string(
    case.get("response")
)


if not request_content or request_content == "{}":
    raise ValueError(
        "requestContent vacío. No se enviará creación al MCP."
    )


if not response_content or response_content == "{}":
    raise ValueError(
        "responseContent vacío. No se enviará creación al MCP."
    )


# ============================================================
# PAYLOAD MCP
# ============================================================

mcp_arguments = {
    "action": "create",
    "name": service_name,
    "deployment": virtual_path,

    # --------------------------------------------------------
    # IMPORTANTE
    # --------------------------------------------------------
    # 9080 es el listener compartido de Parasoft Virtualize.
    # No se debe cambiar a 9081 porque el puerto ya esté ocupado.
    # Que 9080 esté escuchando es precisamente lo esperado.
    # --------------------------------------------------------
    "port": virtualize_port,

    "requestContent": request_content,
    "responseContent": response_content
}


os.makedirs(
    base_output,
    exist_ok=True
)


# Guardamos exactamente lo que se manda al MCP.
with open(
    mcp_payload_path,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        mcp_arguments,
        f,
        ensure_ascii=False,
        indent=2
    )


expected_virtual_url = build_virtual_url(
    virtualize_host,
    virtualize_port,
    virtual_path,
    virtualize_scheme
)


print("======================================")
print("VIRTUALIZATION INFORMATION")
print("======================================")
print(f"Issue:        {issue_key}")
print(f"Service:      {service_name}")
print(f"Virtual Path: {virtual_path}")
print(f"Port:         {virtualize_port}")
print(f"Expected URL: {expected_virtual_url}")
print()


# ============================================================
# HEADERS MCP
# ============================================================

headers = {
    "Authorization": mcp_auth,
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream"
}


# ============================================================
# INITIALIZE MCP
# ============================================================

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


print(
    "INITIALIZE STATUS:",
    init_response.status_code
)

print("INITIALIZE RESPONSE:")
print(init_response.text)


init_response.raise_for_status()


# ============================================================
# OBTENER SESSION ID
# ============================================================

session_id = init_response.headers.get(
    "mcp-session-id"
)


if not session_id:
    raise RuntimeError(
        "MCP session id not returned"
    )


headers["mcp-session-id"] = session_id


print()
print("MCP SESSION:")
print(session_id)
print()


# ============================================================
# CREAR VIRTUALIZACIÓN
# ============================================================

tool_payload = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "manageVirtualServices",
        "arguments": mcp_arguments
    }
}


print("======================================")
print("CREATING VIRTUALIZATION")
print("======================================")

print("MCP ARGUMENTS:")

print(
    json.dumps(
        mcp_arguments,
        ensure_ascii=False,
        indent=2
    )
)


response = requests.post(
    mcp_url,
    headers=headers,
    json=tool_payload,
    timeout=120
)


print()
print(
    "TOOLS STATUS:",
    response.status_code
)

print("TOOLS RESPONSE:")
print(response.text)


# ============================================================
# GUARDAR RESPUESTA MCP
# ============================================================

with open(
    mcp_response_path,
    "w",
    encoding="utf-8"
) as f:

    f.write(
        response.text
    )


response.raise_for_status()


# ============================================================
# VALIDACIÓN INFORMATIVA
# ============================================================

reported_ports = detect_reported_ports(
    response.text
)


for reported_port in reported_ports:

    try:
        reported_port_int = int(reported_port)
    except ValueError:
        continue

    if reported_port_int != virtualize_port:

        print()
        print("======================================")
        print("WARNING - MCP PORT MISMATCH")
        print("======================================")

        print(
            f"[WARN] El MCP informó el puerto "
            f"{reported_port_int}, pero el puerto configurado "
            f"para Virtualize es {virtualize_port}."
        )

        print(
            "[WARN] Se ignorará el puerto informado por MCP "
            "para efectos de documentación."
        )

        print(
            f"[INFO] URL esperada: "
            f"{expected_virtual_url}"
        )

        break


print()
print("======================================")
print("VIRTUALIZATION CREATED SUCCESSFULLY")
print("======================================")

print(
    f"Expected Virtual URL: "
    f"{expected_virtual_url}"
)
