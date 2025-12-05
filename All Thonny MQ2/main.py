import utime
print('Welcome System')
print("MQ2 warm-up...")

from warehouseController import *
utime.sleep(0.1)  # small delay for USB

print("Calibrating MQ2...")
controller = WarehouseAlarmController()
controller.run()

while True:
    time.sleep(0.1)


