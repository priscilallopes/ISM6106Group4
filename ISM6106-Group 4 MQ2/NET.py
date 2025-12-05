import urequests
from Log import *
import network
import time
import secrets

class NET:

    def __init__(self, ssid, password):
        self.ssid = ssid
        self.password = password
        self.wlan = network.WLAN(network.STA_IF)

    def connect(self):
        Log.i("NET: activating WiFi...")
        self.wlan.active(True)

        attempt = 0
        if not self.wlan.isconnected():
            self.wlan.connect(self.ssid, self.password)

        while not self.wlan.isconnected() and attempt < 10:
            attempt += 1
            Log.i(f"NET: connecting... attempt {attempt}")
            time.sleep(1)

        if self.wlan.isconnected():
            ip = self.wlan.ifconfig()[0]
            Log.i(f"NET: connected, IP={ip}")
        else:
            Log.e("NET: FAILED to connect!")

    # -------------- REQUIRED BY THE DAL ----------------
    def post(self, url, payload):
        """Send POST to APEX REST endpoint"""

        Log.i(f"NET: POST {url}")
        Log.i(f"NET: payload = {payload}")

        try:
            response = urequests.post(url, json=payload)
            status = response.status_code
            Log.i(f"NET: POST OK ({status})")
            response.close()
            return status

        except Exception as e:
            Log.e(f"NET: POST ERROR: {e}")
            return None
