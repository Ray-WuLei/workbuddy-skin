# -*- coding: utf-8 -*-
"""Minimal zero-dependency CDP client (stdlib only).

Ships a tiny RFC6455 WebSocket implementation so this tool never breaks
because a pip package is missing from WorkBuddy's bundled interpreter.
"""
import base64
import json
import os
import socket
import struct
import urllib.parse
import urllib.request


class WSError(IOError):
    pass


class WS:
    def __init__(self, url, timeout=10.0):
        u = urllib.parse.urlparse(url)
        host = u.hostname or "127.0.0.1"
        port = u.port or 80
        path = u.path + (("?" + u.query) if u.query else "")
        self.sock = socket.create_connection((host, port), timeout)
        self.sock.settimeout(timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (
            "GET %s HTTP/1.1\r\n"
            "Host: %s:%d\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Key: %s\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n" % (path, host, port, key)
        )
        self.sock.sendall(req.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise WSError("handshake: connection closed")
            buf += chunk
        head, rest = buf.split(b"\r\n\r\n", 1)
        status = head.split(b"\r\n")[0]
        if b" 101 " not in status:
            raise WSError("handshake failed: " + status.decode("latin-1", "replace"))
        self.buf = rest

    # ---- low level ----
    def _read(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise WSError("connection closed")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def _write(self, opcode, data):
        header = bytearray([0x80 | opcode])
        n = len(data)
        mask = os.urandom(4)
        if n < 126:
            header.append(0x80 | n)
        elif n < 65536:
            header.append(0x80 | 126)
            header += struct.pack(">H", n)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", n)
        header += mask
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        self.sock.sendall(bytes(header) + masked)

    def send_text(self, text):
        self._write(0x1, text.encode("utf-8"))

    def recv_text(self):
        chunks = []
        while True:
            b1, b2 = self._read(2)
            fin = b1 & 0x80
            opcode = b1 & 0x0F
            n = b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read(8))[0]
            mask = self._read(4) if (b2 & 0x80) else None
            payload = self._read(n) if n else b""
            if mask:
                payload = bytes(c ^ mask[i % 4] for i, c in enumerate(payload))
            if opcode == 0x8:
                raise WSError("closed by peer")
            if opcode == 0x9:
                self._write(0xA, payload)
                continue
            if opcode == 0xA:
                continue
            if opcode in (0x1, 0x2, 0x0):
                chunks.append(payload)
                if fin:
                    return b"".join(chunks).decode("utf-8", "replace")
                continue
            # ignore other control frames

    def close(self):
        try:
            self._write(0x8, b"")
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass


def list_targets(port=9222, timeout=4.0):
    url = "http://127.0.0.1:%d/json/list" % port
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def pick_page(targets, title_contains="WorkBuddy"):
    pages = [t for t in targets if t.get("type") == "page"]
    for t in pages:
        if title_contains and title_contains.lower() in (t.get("title") or "").lower():
            return t
    return pages[0] if pages else None


class Session:
    """One websocket session bound to one page target."""

    def __init__(self, ws_url, timeout=20.0):
        self.ws = WS(ws_url, timeout=timeout)
        self._id = 0

    def call(self, method, params=None, timeout=25.0):
        self._id += 1
        mid = self._id
        self.ws.send_text(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv_text())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise WSError("CDP error: %s" % msg["error"])
                return msg.get("result", {})

    def eval(self, expression, await_promise=False):
        res = self.call(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": await_promise},
        )
        if res.get("exceptionDetails"):
            desc = res["exceptionDetails"].get("exception", {}).get("description", "js error")
            raise WSError(desc)
        return res.get("result", {}).get("value")

    def close(self):
        self.ws.close()
