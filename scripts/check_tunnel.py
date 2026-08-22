"""Prove that a real PostgreSQL server answers at the far end of the tunnel.

An open TCP port proves nothing: a tunnel can happily forward to nowhere.
So this speaks the first message of the PostgreSQL wire protocol, SSLRequest,
and checks the answer.

    client -> 8 bytes: length=8, request code=80877103
    server -> 1 byte : 'S' (SSL supported) or 'N' (not supported)

Only a PostgreSQL server replies that way, so a single 'S' or 'N' is proof of
identity. No password is sent and no session is opened: the connection is
closed before authentication even starts.

Standard library only, on purpose -- this must be runnable BEFORE the virtual
environment exists.

Usage:  python scripts/check_tunnel.py [host] [port]
Exit code 0 on success, 1 on failure.
"""

import os
import socket
import struct
import sys

SSL_REQUEST_CODE = 80877103  # fixed by the PostgreSQL protocol
TIMEOUT_SECONDS = 10


def main() -> int:
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else int(os.environ.get("MHI_TUNNEL_PORT", 15432))

    # ">ii" = two 32-bit signed integers, big-endian ("network byte order"),
    # which is what the PostgreSQL protocol expects.
    ssl_request = struct.pack(">ii", 8, SSL_REQUEST_CODE)

    try:
        with socket.create_connection((host, port), timeout=TIMEOUT_SECONDS) as sock:
            sock.sendall(ssl_request)
            reply = sock.recv(1)
    except OSError as exc:
        print(f"FAIL: cannot reach {host}:{port} -- {exc}")
        return 1

    if reply == b"S":
        print(f"OK: PostgreSQL answered at {host}:{port} (SSL supported)")
        return 0
    if reply == b"N":
        print(f"OK: PostgreSQL answered at {host}:{port} (SSL not offered -- expected here, the SSH tunnel already encrypts)")
        return 0

    print(f"FAIL: {host}:{port} answered {reply!r}, which is not the PostgreSQL protocol")
    return 1


if __name__ == "__main__":
    sys.exit(main())
