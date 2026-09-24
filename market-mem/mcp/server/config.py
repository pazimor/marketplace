import os


class Config:
    SERVER_PORT: int = int(os.getenv("MEM_PORT", "7333"))

    # Shared secret required on every request (Authorization: Bearer <token>).
    # Empty = no auth, only tolerated when the port is published on loopback.
    MEM_TOKEN: str = os.getenv("MEM_TOKEN", "")

    # Address the port is published on by docker compose (informational — the
    # server itself always binds 0.0.0.0 inside the container). Used to refuse
    # starting unauthenticated when the port is reachable off-host.
    MEM_BIND_ADDR: str = os.getenv("MEM_BIND_ADDR", "127.0.0.1")

    # Hostnames remote clients may use in the Host header, comma-separated
    # (no port). The MCP SSE transport rejects anything else as a possible DNS
    # rebinding attack, so a LAN-exposed server must list its LAN IP / hostname.
    MEM_ALLOWED_HOSTS: str = os.getenv("MEM_ALLOWED_HOSTS", "")

    # TLS cert + key (mkcert). Both set and present = serve https.
    TLS_CERT_FILE: str = os.getenv("TLS_CERT_FILE", "")
    TLS_KEY_FILE: str = os.getenv("TLS_KEY_FILE", "")


config = Config()


LOOPBACK = {"127.0.0.1", "localhost", "::1", "[::1]"}


def bind_is_loopback() -> bool:
    return config.MEM_BIND_ADDR in LOOPBACK


def allowed_hosts() -> list[str]:
    """Host header values accepted by the MCP transport.

    Loopback is always allowed; MEM_ALLOWED_HOSTS adds the addresses remote
    clients dial. Each entry is accepted bare and with any port (`host:*`)."""
    names = ["127.0.0.1", "localhost", "[::1]"]
    names += [h.strip() for h in config.MEM_ALLOWED_HOSTS.split(",") if h.strip()]
    out: list[str] = []
    for n in names:
        out += [n, f"{n}:*"]
    return out


def ssl_kwargs() -> dict[str, str]:
    """uvicorn TLS arguments; empty (plain http) unless cert + key both exist."""
    cert, key = config.TLS_CERT_FILE, config.TLS_KEY_FILE
    if cert and key and os.path.exists(cert) and os.path.exists(key):
        return {"ssl_certfile": cert, "ssl_keyfile": key}
    return {}
