#!/usr/bin/env python3

import json
import logging
import subprocess
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# Project paths
PROJECT_DIR = Path(__file__).resolve().parent.parent
INVENTORY = PROJECT_DIR / "ansible" / "inventory"
PLAYBOOK = PROJECT_DIR / "ansible" / "restart-nginx.yml"

# Webhook settings
HOST = "127.0.0.1"
PORT = 9080

# Prevent repeated recovery attempts
COOLDOWN_SECONDS = 60
last_recovery_time = 0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


class AlertHandler(BaseHTTPRequestHandler):

    def do_POST(self):
        global last_recovery_time

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(content_length))

            status = payload.get("status")
            alerts = payload.get("alerts", [])

            for alert in alerts:
                alert_name = alert.get("labels", {}).get("alertname")

                if alert_name == "NginxWebsiteDown" and status == "firing":

                    current_time = time.time()

                    if current_time - last_recovery_time < COOLDOWN_SECONDS:
                        logging.info("Recovery skipped due to cooldown.")
                        continue

                    logging.warning("NGINX website is down!")
                    logging.info("Starting Ansible recovery playbook...")

                    last_recovery_time = current_time

                    result = subprocess.run(
                        [
                            "ansible-playbook",
                            "-i", str(INVENTORY),
                            str(PLAYBOOK)
                        ],
                        cwd=str(PROJECT_DIR),
                        capture_output=True,
                        text=True,
                        timeout=120
                    )

                    logging.info(result.stdout)

                    if result.returncode == 0:
                        logging.info("NGINX recovery successful.")
                    else:
                        logging.error(result.stderr)

            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Webhook processed")

        except Exception as error:
            logging.exception("Webhook processing failed: %s", error)
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"Webhook processing failed")

    def log_message(self, format, *args):
        logging.info(format % args)


if __name__ == "__main__":
    logging.info("Starting NGINX recovery webhook...")
    server = HTTPServer((HOST, PORT), AlertHandler)
    server.serve_forever()
