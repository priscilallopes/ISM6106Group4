import ujson
from Log import *
from NET import NET

class DAL:

    def __init__(self, net, url, warehouse_id, room_id):
        self.net = net
        self.url = url
        self.warehouse_id = warehouse_id
        self.room_id = room_id

    # ------------------------------------------------------
    # POST WRAPPER
    # ------------------------------------------------------
    def postPayload(self, payload):
        print("DAL: posting", payload)
        # NET.post() is expected to do something like:
        # urequests.post(self.url, json=payload)
        return self.net.post(self.url, payload)

    # ------------------------------------------------------
    # BUILD GENERIC PAYLOAD
    #  - generates timestamp string in format: YYYY-MM-DD HH:MM:SS
    #  - IMPORTANT: includes key "timestamp" to match ORDS bind :timestamp
    # ------------------------------------------------------
    def buildPayload(self,
                     temperature=None,
                     humidity=None,
                     smoke_ppm=None,
                     hydrogen_ppm=None,
                     lpg_ppm=None,
                     methane_ppm=None,
                     room_id=None,
                     sensor_id=None,
                     warehouse_id=None):

        import time
        ts = time.localtime()
        iso_ts = "%04d-%02d-%02d %02d:%02d:%02d" % (
            ts[0], ts[1], ts[2],
            ts[3], ts[4], ts[5]
        )

        # fallbacks to defaults from __init__ if not provided
        if room_id is None:
            room_id = self.room_id
        if warehouse_id is None:
            warehouse_id = self.warehouse_id

        return {
            # >>> THIS is the key your ORDS code expects <<<
            "timestamp": iso_ts,     # maps to :timestamp in PL/SQL

            # you can keep this if you use it elsewhere (not required by ORDS)
            "reading_ts": iso_ts,

            "room_id": room_id,
            "sensor_id": sensor_id,
            "temperature": temperature,
            "humidity": humidity,
            "smoke_ppm": smoke_ppm,
            "hydrogen_ppm": hydrogen_ppm,
            "lpg_ppm": lpg_ppm,
            "methane_ppm": methane_ppm,
            "warehouse_id": warehouse_id
        }

    # ------------------------------------------------------
    # TEMPERATURE-ONLY PUBLIC METHOD  (your controller calls this)
    # ------------------------------------------------------
    def postTemperature(self, temperature, sensor_id=202):
        payload = self.buildPayload(
            temperature=temperature,
            humidity=None,
            smoke_ppm=None,
            hydrogen_ppm=None,
            lpg_ppm=None,
            methane_ppm=None,
            room_id=self.room_id,
            sensor_id=sensor_id,
            warehouse_id=self.warehouse_id
        )
        return self.postPayload(payload)