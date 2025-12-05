import utime
from Log import *
from Sensors_advanced import GasSensor
from Counters import SoftwareTimer
from Button import Button
from LightStrip import LightStrip
from Buzzer import PassiveBuzzer
from Displays import LCDDisplay
from warehouseStateModel import *
from DAL import DAL
from NET import NET
import secrets

RED    = (255, 0, 0)
YELLOW = (255, 255, 0)
GREEN  = (0, 255, 0)

STATE_NORMAL  = 0
STATE_WARNING = 1
STATE_ALARM   = 2

ROOM_ID   = 101
SENSOR_ID = 201


class WarehouseAlarmController:

    def __init__(self):

        Log.i("Initializing GAS-Only Alarm System...")

        # GAS SENSOR
        self.gas = GasSensor(pin=26, name="mq2")

        # ACTUATORS
        self.buzzer = PassiveBuzzer(pin=15, name="buzzer")
        self.light  = LightStrip(pin=7, name="lightstrip", numleds=8, brightness=0.5)
        self.display = LCDDisplay(sda=0, scl=1)
        self.resetButton = Button(pin=17, name="reset", handler=None)

        # NETWORK + DATABASE
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

        # TRANSITIONS (original behavior)
        self.model.addTransition(STATE_NORMAL,  ["gas_warning"], STATE_WARNING)
        self.model.addTransition(STATE_NORMAL,  ["gas_alarm"],   STATE_ALARM)
        self.model.addTransition(STATE_WARNING, ["gas_alarm"],   STATE_ALARM)
        self.model.addTransition(STATE_ALARM,   ["reset_event"], STATE_NORMAL)

        # TIMER
        self.sensorTimer = SoftwareTimer("sensorpoll", None)
        self.model.addTimer(self.sensorTimer)

        # OLD WORKING THRESHOLDS
        self.WARNING_GAS = 70
        self.ALARM_GAS   = 90
        self.gas_bad_count = 0

        self._alarmon = False

        Log.i("GAS-Only Warehouse Alarm Ready.")

    # ======================================================
    # STATE ENTERED
    # ======================================================
    def stateEntered(self, state, event):

        Log.i(f"ENTER state={state}, event={event}")

        if state == STATE_NORMAL:
            self._alarmoff()
            self.display.clear()
            self.display.showText("NORMAL SYSTEM", 0, 0)
            self.light.setColor(GREEN)

        elif state == STATE_WARNING:
            self.display.clear()
            self.display.showText("WARNING", 0, 0)
            self.display.showText("CHECK GAS SENSOR", 1, 0)
            self.light.setColor(YELLOW)

        elif state == STATE_ALARM:
            Log.e("!!! GAS ALARM !!!")
            self.display.clear()
            self.display.showText("*** GAS ALARM ***", 0, 0)
            self.display.showText("PRESS RESET!", 1, 0)

            self._alarmon = True
            self.light.setColor(RED)
            self.buzzer.play(1200)

    # ======================================================
    # STATE LEFT
    # ======================================================
    def stateLeft(self, state, event):

        Log.i(f"LEAVE state={state}, event={event}")

        if state == STATE_WARNING:
            self.light.off()
            self.light.setColor(GREEN)

        if state == STATE_ALARM:
            self._alarmon = False
            self._alarmoff()
            self.light.off()
            self.light.setColor(GREEN)

    # ======================================================
    # EVENT HANDLER
    # ======================================================
    def stateEvent(self, state, event):

        # RESET during alarm
        if event == "reset_press" and state == STATE_ALARM:
            Log.i("RESET pressed — clearing GAS ALARM")
            self._alarmon = False
            self._alarmoff()
            self.gas_bad_count = 0
            self.model.processEvent("reset_event")
            return True

        # Periodic reading
        if event == "sensorpoll_timeout":
            self._read_gas()
            self.sensorTimer.start(10)
            return True

        return False

    # ======================================================
    # STATE DO (WARNING ONLY – blinking)
    # ======================================================
    def stateDo(self, state):

        if state == STATE_WARNING:
            self.light.setColor(YELLOW)
            utime.sleep(0.12)
            self.light.off()
            utime.sleep(0.12)

        if state == STATE_ALARM:
            self._alarm_pattern()

    # ======================================================
    # Alarm flashing + buzzer sequence
    # ======================================================
    def _alarm_pattern(self):

        if not self._alarmon:
            return

        self.light.setColor(RED)
        self.buzzer.play(1200)
        utime.sleep(0.12)

        if not self._alarmon:
            return

        self.light.off()
        self.buzzer.play(900)
        utime.sleep(0.12)

    # ======================================================
    # READ GAS SENSOR + POST + THRESHOLDS
    # ======================================================
    def _read_gas(self):

        ratio = self.gas.rawValue()
        readings = self.gas.getGasConcentrations()

        gas = readings["Smoke"]
        hydrogen = readings["Hydrogen"]
        lpg = readings["LPG"]
        methane = readings["Methane"]

        Log.i(f"Gas ratio={ratio}")
        Log.i(f"LPG={lpg}, gas={gas}, Hydrogen={hydrogen}, Methane={methane}")

        # ------- POST DATA --------
        payload = self.dal.buildPayload(
            temp_c=None,
            humidity=None,
            gas=gas,
            hydrogen_ppm=hydrogen,
            lpg_ppm=lpg,
            methane_ppm=methane,
            room_id=ROOM_ID,
            sensor_id=SENSOR_ID
        )

        self.dal.postPayload(payload)

        # -------- ORIGINAL THRESHOLD LOGIC --------

        # WARNING threshold
        if gas >= self.WARNING_GAS:
            self.model.processEvent("gas_warning")

        # ALARM threshold, 3 consecutive readings
        if gas >= self.ALARM_GAS:
            self.gas_bad_count += 1

            if self.gas_bad_count >= 3:
                self.model.processEvent("gas_alarm")
        else:
            self.gas_bad_count = 0

    # ======================================================
    # HELPERS
    # ======================================================
    def _alarmoff(self):
        try:
            self.buzzer.stop()
        except:
            pass

    # ======================================================
    # RUN
    # ======================================================
    def run(self):
        Log.i("Starting gas polling timer (10 sec)...")
        self.sensorTimer.start(10)
        self.model.run()

    def stop(self):
        self.model.stop()
