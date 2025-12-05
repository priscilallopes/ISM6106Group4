import time
print('Welcome System')
from warehouseController import *
time.sleep(0.1)  # small delay for USB

controller = WarehouseAlarmController()
controller.run()

while True:
    time.sleep(0.1)