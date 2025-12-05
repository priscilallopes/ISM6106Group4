# ---------------------------------------------------------
# mq2.py  (FINAL VERSION - CORRECT DATASHEET CURVES)
# ---------------------------------------------------------

from machine import Pin, ADC
from micropython import const
import utime
from math import log10


# =========================================================
# BASE MQ CLASS  (must appear BEFORE MQ2)
# =========================================================
class BaseMQ(object):

    MQ_SAMPLE_TIMES = const(5)
    MQ_SAMPLE_INTERVAL = const(500)
    MQ_HEATING_PERIOD = const(60000)
    MQ_COOLING_PERIOD = const(90000)

    STRATEGY_FAST = const(1)
    STRATEGY_ACCURATE = const(2)

    def __init__(self, pinData, pinHeater=-1, boardResistance=10,
                 baseVoltage=3.3, measuringStrategy=STRATEGY_ACCURATE):

        self._heater = False
        self._cooler = False
        self._ro = -1.0
        self._stateCalibrate = False

        self._boardResistance = float(boardResistance)
        self._baseVoltage = float(baseVoltage)
        self.measuringStrategy = measuringStrategy

        self.pinData = ADC(pinData)

        # Optional heater pin
        if pinHeater != -1:
            self._useSeparateHeater = True
            self._pinHeater = Pin(pinHeater, Pin.OUT)
        else:
            self._useSeparateHeater = False

    # -----------------------------------------------------
    # CALIBRATION — performed in clean air (important!)
    # -----------------------------------------------------
    def calibrate(self, ro=-1.0):
        print("Calibrating MQ sensor...")

        rs_sum = 0.0
        valid = 0

        for i in range(self.MQ_SAMPLE_TIMES):
            print("  Step", i + 1)
            raw = self.pinData.read_u16()
            rs = self._calculateRS(raw)
            if rs > 0:
                rs_sum += rs
                valid += 1
            utime.sleep_ms(self.MQ_SAMPLE_INTERVAL)

        if valid == 0:
            raise RuntimeError("Calibration failed: RS = 0 for all samples.")

        rs_avg = rs_sum / valid
        ro = rs_avg / self.getRoInCleanAir()

        if ro <= 0:
            raise RuntimeError("Calibration produced invalid RO.")

        self._ro = float(ro)
        self._stateCalibrate = True
        print("Calibration done. RO =", self._ro)

    # -----------------------------------------------------
    # INTERNAL: Calculate RS from ADC reading
    # -----------------------------------------------------
    def _calculateRS(self, rawAdc):
        vrl = rawAdc * (self._baseVoltage / 65535.0)
        eps = 1e-6

        if vrl < eps:
            vrl = eps
        if (self._baseVoltage - vrl) < eps:
            vrl = self._baseVoltage - eps

        return (self._baseVoltage - vrl) / vrl * self._boardResistance

    # -----------------------------------------------------
    # INTERNAL: read RS with averaging
    # -----------------------------------------------------
    def _readRS(self):
        if self.measuringStrategy == self.STRATEGY_ACCURATE:
            rs_sum = 0.0
            for _ in range(self.MQ_SAMPLE_TIMES):
                raw = self.pinData.read_u16()
                rs_sum += self._calculateRS(raw)
                utime.sleep_ms(self.MQ_SAMPLE_INTERVAL)
            return rs_sum / self.MQ_SAMPLE_TIMES

        else:
            raw = self.pinData.read_u16()
            return self._calculateRS(raw)

    # -----------------------------------------------------
    # PUBLIC: Read RS/RO ratio
    # -----------------------------------------------------
    def readRatio(self):
        if not self._stateCalibrate:
            raise RuntimeError("ERROR: MQ sensor NOT calibrated — call calibrate() first")
        rs = self._readRS()
        return rs / self._ro

    # -----------------------------------------------------
    # GAS CURVE HELPER
    # -----------------------------------------------------
    def _ppm_from_ratio(self, ratio, m, b):
        if ratio <= 0:
            return 0
        return 10 ** ((log10(ratio) - b) / m)

    # Every MQ sensor type must define its clean air RO ratio
    def getRoInCleanAir(self):
        raise NotImplementedError("getRoInCleanAir must be implemented by subclass")



# =========================================================
# MQ2 SENSOR — using true datasheet curves
# =========================================================
class MQ2(BaseMQ):

    # Clean air RS/RO ratio from the MQ2 datasheet graph
    MQ2_RO_BASE = 9.83

    def __init__(self, pinData, pinHeater=-1, boardResistance=10,
                 baseVoltage=3.3,
                 measuringStrategy=BaseMQ.STRATEGY_ACCURATE):

        super().__init__(pinData, pinHeater, boardResistance,
                         baseVoltage, measuringStrategy)

    # -----------------------------------------------------
    # GAS PPM CALCULATIONS (official MQ-2 curves)
    # -----------------------------------------------------

    def readLPG(self):
        # Datasheet: slope=-0.47, intercept=1.41
        ratio = self.readRatio()
        return self._ppm_from_ratio(ratio, -0.47, 1.41)

    def readMethane(self):
        # Datasheet: slope=-0.38, intercept=1.50
        ratio = self.readRatio()
        return self._ppm_from_ratio(ratio, -0.38, 1.50)

    def readSmoke(self):
        # Datasheet: slope=-0.43, intercept=1.70
        ratio = self.readRatio()
        return self._ppm_from_ratio(ratio, -0.43, 1.70)

    def readHydrogen(self):
        # Datasheet: slope=-0.48, intercept=1.57
        ratio = self.readRatio()
        return self._ppm_from_ratio(ratio, -0.48, 1.57)

    # MQ2-specific clean air RO value
    def getRoInCleanAir(self):
        return self.MQ2_RO_BASE
