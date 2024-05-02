# import main module
try:
    import uasyncio as asyncio
    from machine import I2C, Pin
    from ads1x15 import ADS1115
    i2c = I2C(0, sda=Pin(8), scl=Pin(9))
    ads1115 = ADS1115(i2c, address=72, gain=1)
    import onewire
    import ds18x20
    ds_sensor = ds18x20.DS18X20(onewire.OneWire(Pin(21)))

except ImportError:
    import asyncio
    from unittest.mock import Mock, MagicMock
    ads1115 = Mock()
    ads1115.read = Mock(return_value=2096)
    ads1115.raw_to_v = Mock(return_value=2.5)

    def raw_to_v(arg):
        return 4096/arg
    ads1115.raw_to_v.side_effect = raw_to_v
    ds18x20 = Mock()
    ds_sensor = Mock()
    ds_sensor.scan = Mock(return_value=[1])
    ds_sensor.convert_temp = Mock()
    ds_sensor.read_temp = Mock(return_value=25.5)

import web
from lib.microdot.microdot import send_file

# Variables
ph = None
tds = None
temp = None


# define async functions here
async def test_extension():
    # Web UI extensions also can be added to main web.py module
    @web.app.route('/ph')
    async def test(request):
        response = send_file("ph/static/ph.html", compressed=False,
                             file_extension="")
        return response

    print("Test extension")
    # Control main module from extension:
    web.mac_address = 1111444


async def read_sensors():
    def calculate_average(values):
        #print(f"Calculete average, len: {len(values)}")
        if len(values) > 0:
            average = sum(values) / len(values)
            return round(average, 4)
        else:
            return None

    global ph
    global temp
    global tds
    temp_sensors = ds_sensor.scan()
    print("Start sensor reading worker")

    ph_buffer = []
    tds_buffer = []
    temp_buffer = []

    while 1:
        for _ in range(5):
            # PH
            _value = ads1115.read(0, 0)
            ph_adc = ads1115.raw_to_v(_value)
            ph_buffer.append(ph_adc)

            # TDS
            _value = ads1115.read(0, 3)
            tds_adc = ads1115.raw_to_v(_value)
            tds_buffer.append(tds_adc)

            # Temp
            if temp_sensors:
                ds_sensor.convert_temp()
                _temp = ds_sensor.read_temp(temp_sensors[0])
                temp_buffer.append(_temp)
            await asyncio.sleep(0.5)
        if ph_buffer:
            ph = calculate_average(ph_buffer)
            ph_buffer = []
            print("PH: ", ph)
        if tds_buffer:
            tds = calculate_average(tds_buffer)
            tds_buffer = []
            print("TDS: ", tds)
        if temp_buffer:
            temp = calculate_average(temp_buffer)
            temp_buffer = []
            print("Temp: ", temp)


# Define extension async tasks here
extension_tasks = [test_extension, read_sensors]

# Define navbar extension here
extension_navbar = [{"name": "PH", "link": "/ph"}]
