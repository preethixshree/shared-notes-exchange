"""Run a local CGI-enabled server for the assignment.

Open http://localhost:8000/form.html after starting this file.
"""

import os
import subprocess
import sys
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse


HOST = "localhost"
PORT = 8000
SCRIPT_URL = "/cgi-bin/process_user.cgi"
SCRIPT_PATH = os.path.join("cgi-bin", "process_user.cgi")


class AssignmentCGIHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urlparse(self.path)

        if parsed_url.path == SCRIPT_URL:
            self.run_cgi_script(parsed_url.query.encode("utf-8"))
            return

        super().do_GET()

    def do_POST(self):
        parsed_url = urlparse(self.path)

        if parsed_url.path == SCRIPT_URL:
            length = int(self.headers.get("Content-Length", "0"))
            self.run_cgi_script(self.rfile.read(length))
            return

        self.send_error(HTTPStatus.NOT_FOUND, "CGI endpoint not found")

    def run_cgi_script(self, request_body):
        script_path = os.path.abspath(SCRIPT_PATH)
        parsed_url = urlparse(self.path)

        env = os.environ.copy()
        env.update({
            "REQUEST_METHOD": self.command,
            "CONTENT_TYPE": self.headers.get("Content-Type", ""),
            "CONTENT_LENGTH": str(len(request_body)),
            "HTTP_ACCEPT": self.headers.get("Accept", ""),
            "QUERY_STRING": parsed_url.query,
        })

        result = subprocess.run(
            [sys.executable, script_path],
            input=request_body,
            capture_output=True,
            env=env,
            check=False,
        )

        if result.returncode != 0:
            self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
            self.end_headers()
            self.wfile.write(result.stderr)
            return

        header_blob, _, body = result.stdout.partition(b"\r\n\r\n")
        if not body:
            header_blob, _, body = result.stdout.partition(b"\n\n")

        self.send_response(HTTPStatus.OK)
        for header_line in header_blob.decode("utf-8").splitlines():
            if ":" in header_line:
                name, value = header_line.split(":", 1)
                self.send_header(name.strip(), value.strip())
        self.end_headers()
        self.wfile.write(body)


def main():
    server = ThreadingHTTPServer((HOST, PORT), AssignmentCGIHandler)
    print(f"Serving CGI demo at http://{HOST}:{PORT}/form.html")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
