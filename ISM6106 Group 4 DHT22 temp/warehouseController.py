import utime
from Log import *
from Sensors_advanced import DHTSensor
from Counters import SoftwareTimer
from Button import Button
from LightStrip import LightStrip
from Buzzer import PassiveBuzzer
from Displays import LCDDisplay
from warehouseStateModel import *
from DAL import DAL
from NET import NET

# ----- CONSTANTS -----
RED    = (255, 0, 0)
YELLOW = (255, 255, 0)
GREEN  = (0, 255, 0)
STATE_NORMAL  = 0
STATE_WARNING = 1
STATE_ALARM   = 2
ROOM_ID   = 102     # Temperature Room
SENSOR_ID = 202     # Temperature Sensor


class WarehouseAlarmController:

    def __init__(self):

        Log.i("Initializing TEMP-Only Alarm System...")

        self.dht = DHTSensor(pin=3, sensor_type="DHT22", name="dht")
        self.buzzer = PassiveBuzzer(pin=15, name="buzzer")
        self.light  = LightStrip(pin=7, name="lightstrip", numleds=8, brightness=0.5)
        self.display = LCDDisplay(sda=0, scl=1)
        self.resetButton = Button(pin=17, name="reset", handler=None)

        # ----- NET + DAL -----
        self.net = NET("YOUR_WIFI_SSID", "YOUR_WIFI_PASSWORD")

        self.dal = DAL(
            net=self.net,
            url="https://oracleapex.com/ords/priscilallopes/api/sensor-readings",
            warehouse_id=1,   
            room_id=ROOM_ID  
        )

        # Connect WiFi
        self.net.connect()

        # ----- STATE MACHINE -----
        machine = WarehouseStateMachine(self, debug=True)
        self.model = machine.model

        self.model.addButton(self.resetButton)

        # Sensor poll timer (10 sec)
        self.sensorTimer = SoftwareTimer("sensorpoll", None)
        self.model.addTimer(self.sensorTimer)

        # ----- Threshold logic -----
        self.temp_bad_count = 0
        self.WARNING_TEMP = 30
        self.ALARM_TEMP   = 45
        self._alarmon = False

        Log.i("TEMP-Only Warehouse Alarm Ready.")


    # ======================================================
    #  STATE ENTERED
    # ======================================================
    def stateEntered(self, state, event):
        Log.i(f"ENTER state={state}, event={event}")

        if state == STATE_NORMAL:
            self.temp_bad_count = 0
            self._alarmoff()
            self.display.clear()
            self.display.showText("NORMAL SYSTEM", 0, 0)
            self.light.setColor(GREEN)

        elif state == STATE_WARNING:
            self.display.clear()
            self.display.showText("WARNING", 0, 0)
            self.display.showText("CHECK SENSOR", 1, 0)
            self.light.setColor(YELLOW)

        elif state == STATE_ALARM:
            Log.e("!!! ALARM TRIGGERED !!!")
            self.display.clear()
            self.display.showText("*** ALARM ***", 0, 0)
            self.display.showText("PRESS RESET!", 1, 0)

            self._alarmon = True
            self.light.setColor(RED)
            self.buzzer.play(1200)


    # ======================================================
    #  STATE LEFT
    # ======================================================
    def stateLeft(self, state, event):
        Log.i(f"LEAVE state={state}, event={event}")

        if state == STATE_ALARM:
            self._alarmon = False
            self._alarmoff()
            self.light.off()
            self.light.setColor(GREEN)


    # ======================================================
    #  STATE EVENT
    # ======================================================
    def stateEvent(self, state, event):

        # RESET during ALARM
        if event == "reset_press" and state == STATE_ALARM:
            Log.i("RESET pressed — clearing ALARM")
            self._alarmon = False
            self._alarmoff()
            self.model.processEvent("reset_event")
            return True

        # TIMER event: read sensors
        if event == "sensorpoll_timeout":
            self._read_temp()
            self.sensorTimer.start(10)
            return True

        return False


    # ======================================================
    #  STATE DO LOOP
    # ======================================================
    def stateDo(self, state):
        if state == STATE_ALARM:
            self._alarm_pattern()


    # ======================================================
    #  FLASHING + TONE ALARM PATTERN
    # ======================================================
    def _alarm_pattern(self):

        if not self._alarmon:
            return

        # Tone 1200 Hz, RED LED
        self.light.setColor(RED)
        self.buzzer.play(1200)
        utime.sleep(0.12)

        if not self._alarmon:
            return

        # Tone 900 Hz, LED OFF
        self.light.off()
        self.buzzer.play(900)
        utime.sleep(0.12)


    # ======================================================
    #  SENSOR READING + POST TO ORACLE
    # ======================================================
    def _read_temp(self):

        data = self.dht.rawValue()
        temperature = data.temperature
        hum  = data.humidity   # optional: keep if you like logging

        Log.i(f"Temperature={temperature}, Hum={hum}")

        # ---------- TEMP-ONLY POST ----------
        self.dal.postTemperature(
            temperature=temperature,
            sensor_id=SENSOR_ID   # 202, as defined at top of file
        )

        # WARNING / ALARM logic (unchanged)
        if temperature >= self.ALARM_TEMP:
            self.temp_bad_count += 1
            if self.temp_bad_count == 1:
                self.model.processEvent("temp_warning")
            if self.temp_bad_count >= 3:
                self.model.processEvent("temp_alarm")
        else:
            self.temp_bad_count = 0


    # ======================================================
    #  HELPERS
    # ======================================================
    def _alarmoff(self):
        try:
            self.buzzer.stop()
        except:
            pass


    # ======================================================
    #  RUN / STOP
    # ======================================================
    def run(self):
        Log.i("Starting sensor timer (10 sec)...")
        self.sensorTimer.start(10)
        self.model.run()

    def stop(self):
        self.model.stop()
