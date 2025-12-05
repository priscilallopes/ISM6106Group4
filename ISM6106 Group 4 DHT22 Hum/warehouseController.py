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
import secrets

# ----------------------------------------------------------
# CONSTANTS
# ----------------------------------------------------------
RED    = (255, 0, 0)
YELLOW = (255, 255, 0)
GREEN  = (0, 255, 0)

STATE_NORMAL  = 0
STATE_WARNING = 1
STATE_ALARM   = 2

ROOM_ID   = 103
SENSOR_ID = 203     # HUMIDITY sensor


class WarehouseAlarmController:

    def __init__(self):

        Log.i("Initializing HUM-Only Alarm System...")

        # -------- DEVICES --------
        self.dht = DHTSensor(pin=3, sensor_type="DHT22", name="dht")
        self.buzzer = PassiveBuzzer(pin=15, name="buzzer")
        self.light  = LightStrip(pin=7, name="lightstrip", numleds=8, brightness=0.5)
        self.display = LCDDisplay(sda=0, scl=1)
        self.resetButton = Button(pin=17, name="reset", handler=None)

        # -------- NETWORK + DAL --------
        self.net = NET(secrets.SSID, secrets.PASSWORD)

        self.dal = DAL(
            net=self.net,
            url="https://oracleapex.com/ords/priscilallopes/api/sensor-readings",
            warehouse_id=1,
            room_id=ROOM_ID
        )

        self.net.connect()

        # -------- STATE MACHINE --------
        machine = WarehouseStateMachine(self, debug=True)
        self.model = machine.model

        self.model.addButton(self.resetButton)

        # Custom humidity events
        self.model.addCustomEvent("hum_warning")
        self.model.addCustomEvent("hum_alarm")

        # Transitions
        self.model.addTransition(STATE_NORMAL,  ["hum_warning"], STATE_WARNING)
        self.model.addTransition(STATE_WARNING, ["hum_alarm"],   STATE_ALARM)
        self.model.addTransition(STATE_ALARM,   ["reset_event"], STATE_NORMAL)

        # Timer
        self.sensorTimer = SoftwareTimer("sensorpoll", None)
        self.model.addTimer(self.sensorTimer)

        # HUMIDITY LIMITS
        self.hum_bad_count = 0
        self.WARNING_HUM = 70
        self.ALARM_HUM   = 85

        # Alarm flag used by _alarm_pattern
        self._alarmon = False

        Log.i("HUM-Only Warehouse Alarm Ready.")


    # ======================================================
    # STATE ENTERED
    # ======================================================
    def stateEntered(self, state, event):

        Log.i(f"ENTER state={state}, event={event}")

        if state == STATE_NORMAL:
            # Fully reset alarm state
            self._alarmon = False
            self.hum_bad_count = 0
            self._alarmoff()

            self.display.clear()
            self.display.showText("NORMAL SYSTEM", 0, 0)
            self.light.setColor(GREEN)

        elif state == STATE_WARNING:
            self.display.clear()
            self.display.showText("WARNING", 0, 0)
            self.display.showText("CHECK HUMIDITY", 1, 0)
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
    # STATE LEFT
    # ======================================================
    def stateLeft(self, state, event):

        Log.i(f"LEAVE state={state}, event={event}")

        if state == STATE_ALARM:
            # Make absolutely sure alarm is disabled
            self._alarmon = False
            self._alarmoff()

            # Reset lights for the next state
            self.light.off()
            # NORMAL state will set GREEN again in stateEntered


    # ======================================================
    # STATE EVENT
    # ======================================================
    def stateEvent(self, state, event):

        # RESET BUTTON during alarm
        if event == "reset_press" and state == STATE_ALARM:
            Log.i("RESET pressed — clearing ALARM")
            # Stop alarm immediately
            self._alarmon = False
            self._alarmoff()
            self.hum_bad_count = 0
            # Transition back to NORMAL
            self.model.processEvent("reset_event")
            return True

        # TIMER event → read sensor
        if event == "sensorpoll_timeout":
            self._read_humidity()
            self.sensorTimer.start(10)
            return True

        return False


    # ======================================================
    # STATE DO (KEEP ALARM FLASHING)
    # ======================================================
    def stateDo(self, state):
        if state == STATE_ALARM:
            self._alarm_pattern()


    # ======================================================
    # ALARM FLASH + TONE PATTERN
    # ======================================================
    def _alarm_pattern(self):

        # If someone has cleared the alarm, do nothing
        if not self._alarmon:
            return

        # First tone (HIGH) + RED
        self.light.setColor(RED)
        self.buzzer.play(1200)
        utime.sleep(0.12)
        # Ensure tone is not left latched
        self.buzzer.stop()

        if not self._alarmon:
            return

        # Second tone (LOW) + lights OFF
        self.light.off()
        self.buzzer.play(900)
        utime.sleep(0.12)
        # Again, ensure buzzer is off at the end of the cycle
        self.buzzer.stop()


    # ======================================================
    # READ HUMIDITY + POST
    # ======================================================
    def _read_humidity(self):

        data = self.dht.rawValue()
        temp = data.temperature
        hum  = data.humidity

        Log.i(f"Temp={temp}, Hum={hum}")

        # ------- BUILD PAYLOAD --------
        payload = self.dal.buildPayload(
            temp_c=None,
            humidity=hum,
            smoke_ppm=None,
            hydrogen_ppm=None,
            lpg_ppm=None,
            methane_ppm=None,
            room_id=ROOM_ID,
            sensor_id=SENSOR_ID
        )

        self.dal.postPayload(payload)

        # ------- HUMIDITY WARNING / ALARM --------
        if hum >= self.ALARM_HUM:
            self.hum_bad_count += 1

            if self.hum_bad_count == 1:
                self.model.processEvent("hum_warning")

            if self.hum_bad_count >= 3:
                self.model.processEvent("hum_alarm")

        else:
            # Below alarm threshold → reset counter
            self.hum_bad_count = 0


    # ======================================================
    # HELPERS
    # ======================================================
    def _alarmoff(self):
        try:
            self.buzzer.stop()
        except:
            pass


    # ======================================================
    # RUN LOOP
    # ======================================================
    def run(self):
        Log.i("Starting sensor timer (10 sec)...")
        self.sensorTimer.start(10)
        self.model.run()

    def stop(self):
        self.model.stop()
