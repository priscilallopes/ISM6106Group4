from Sensors import *
class GasSensor(Sensor):
    def __init__(self, pin, name='GasSensor', lowActive=False,
                 threshold=1.5, baseVoltage=3.3):
        super().__init__(name, lowActive)

        from mq2 import MQ2
        self._mq2 = MQ2(pin, baseVoltage=baseVoltage)
        self._threshold = threshold

        print("GasSensor: warming up...")
        utime.sleep(2)

        print("GasSensor: calibrating in clean air...")
        self._mq2.calibrate()
        print("GasSensor: calibration complete.")

    def rawValue(self):
        """Return RS/RO ratio (≈1 in clean air)"""
        try:
            return self._mq2.readRatio()
        except Exception as e:
            print("GasSensor rawValue error:", e)
            return -1

    def tripped(self):
        ratio = self.rawValue()
        if ratio < 0:
            return False

        if self._lowActive:
            return ratio < self._threshold
        else:
            return ratio >= self._threshold

    def getGasConcentrations(self):
        try:
            return {
                'LPG': self._mq2.readLPG(),
                'Smoke': self._mq2.readSmoke(),
                'Hydrogen': self._mq2.readHydrogen(),
                'Methane': self._mq2.readMethane()
            }
        except Exception as e:
            print("GasSensor concentration error:", e)
            return {
                'LPG': 0,
                'Smoke': 0,
                'Hydrogen': 0,
                'Methane': 0
            }
