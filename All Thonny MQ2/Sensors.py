"""
# Sensors.py
# A simple Sensor hierarchy for digital and analog sensors
# Added support for Ultrasonic Sensor on 9/11/23
# Added support for DHT11/DHT22 sensor on 6/14/24
# Author: Arijit Sengupta
"""

import utime
import math
from machine import Pin, ADC
from Log import *

class Sensor:
    """
    The top level sensor class - assume each sensor uses 
    at least one pin. We do not create the IO here because
    some sensors may use Analog inputs
    
    Parameters
    --------
    lowActive: set to True if the sensor gets low (or under threshold)
    when tripped. So an analog light sensor should normally get a high
    value but when covered, go low. So lowActive should be True
    
    A force sensor would be opposite - tripped when force gets high
    so lowActive should be False.

    Some of the digital sensors such as flame sensors, proximity sensors
    are lowActive, while others such as PIR sensors are highActive. Please
    check the sensor documentation for the correct value.
    """
    
    def __init__(self, name='Sensor', lowActive = True):
        self._lowActive = lowActive
        self._name = name

    def rawValue(self):
        Log.e(f"rawValue not implemented for {type(self).__name__} {self._name}")

    def tripped(self)->bool:
        Log.e(f"tripped not implemented for {type(self).__name__} {self._name}")
        return False

class DigitalSensor(Sensor):
    """
    A simple digital sensor (like the commonly available LC-393 that is a light sensor)
    has a digital output that flips based on a manual threshold control

    We are just going to poll this to keep things simple.

    Parameters
    --------
    pin: the pin number to which the sensor is connected
    name: the name of the sensor
    lowActive: set to True if the sensor gets low when tripped.
    """

    def __init__(self, pin, name='Digital Sensor', lowActive=True, handler=None):
        super().__init__(name, lowActive)
        self._pinio = Pin(pin, Pin.IN)
        self._handler = None
        self.setHandler(handler)

    def rawValue(self):
        return self._pinio.value()
    
    def tripped(self)->bool:
        v = self.rawValue()
        if (self._lowActive and v == 0) or (not self._lowActive and v == 1):
            Log.i(f"DigitalSensor {self._name}: sensor tripped")
            return True
        else:
            return False
        
    def setHandler(self, handler):
        """ 
	    set the handler to a new handler. Pass None to remove existing handler
	    """
        
        # if the old handler was active already, or if the new handler is None, remove the irq
        if self._handler is not None or handler is None:
            self._pinio.irq(handler = None)
    
        # Now set it to th enew handler
        self._handler = handler
        # Create the IRQ if the handler is not None
        if self._handler:
            self._pinio.irq(trigger = Pin.IRQ_FALLING | Pin.IRQ_RISING, handler = self._callback)
        
    def _callback(self, pin):
        """ The private interrupt handler - will call appropriate handlers """
        
        if self._handler is not None:
            if self.tripped():
                Log.i(f'Sensor {self._name} tripped')
                self._handler.sensorTripped(self._name)
            else:
                Log.i(f'Sensor {self._name} untripped')
                self._handler.sensorUntripped(self._name)

class AnalogSensor(Sensor):
    """
    A simple analog sensor that returns a voltage or voltage ratio output
    that can be read in using an ADC. Pico reads in via a 16bit unsigned

    Since analog sensors do not have a handler, you need to poll
    the rawValue() method to get its value. The tripped method takes
    3 readings and takes the average. If the average is higher/lower
    than the threshold it will return true.
    
    Most analog sensors such as LDRs and thermistors will require
    a 10K pull-up resistor to the 3.3V rail. For better results,
    connect the sensor between the ADC pin and AGND (pin 33).
    Thermistor has a separate class - see below).
    
    Set the lowActive to True if rawValue gets lower when the sensor
    is tripped. You may need to set the threshold appropriately for
    your application.
    """
    
    def __init__(self, pin, name='Analog Sensor', lowActive=True, threshold = 30000):
        """ analog sensors will need to be sent a threshold value to detect trip """
        
        super().__init__(name, lowActive)
        self._pinio = ADC(pin)
        self._threshold = threshold

    def tripped(self)->bool:
        """ sensor is tripped if sensor value is higher or lower than threshold """
        
        # Take 3 measurements after 0.1 sec to get an average
        v1 = self.rawValue()
        utime.sleep(0.1)
        v2 = self.rawValue()
        utime.sleep(0.1)
        v3 = self.rawValue()
        
        v = (v1 + v2 + v3) / 3
        
        if (self._lowActive and v < self._threshold) or (not self._lowActive and v > self._threshold):
            Log.i(f"AnalogSensor {self._name}: sensor tripped")
            return True
        else:
            return False

    def rawValue(self):
        return self._pinio.read_u16()


