#!/usr/bin/env python
"""Start a simple HTTP server on the project’s virtual-env Python."""

from __future__ import annotations

import http.server
import os
import socketserver

PORT = int(os.getenv("PORT", 8000))
Handler = http.server.SimpleHTTPRequestHandler
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Serving at http://localhost:{PORT}")
    httpd.serve_forever()
