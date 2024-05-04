# import main module

try:
    import uasyncio as asyncio
    from machine import I2C, Pin
    from ulab import numpy as np
    from machine import I2C, Pin

    import onewire
    import ds18x20
    from ads1x15 import ADS1115

    ds_sensor = ds18x20.DS18X20(onewire.OneWire(Pin(21)))

except ImportError:
    import asyncio
    import numpy as np
    from unittest.mock import Mock, MagicMock

    i2c = 123
    Pin = Mock()
    ds18x20 = Mock()
    ds_sensor = Mock()
    ds_sensor.scan = Mock(return_value=[1])
    ds_sensor.convert_temp = Mock()
    ds_sensor.read_temp = Mock(return_value=25.5)
    print("Mocking ads1115")


    class ADS1115:
        def __init__(self, *args):
            print("Init ADS1115")

        def read(self):
            # Implement mock behavior for the read method
            return 100  # Return a dummy value

        def raw_to_v(self):
            return 1.55

import web
from lib.stepper_doser_math import linear_interpolation
import json
from lib.microdot.microdot import send_file
from lib.microdot.sse import with_sse

# Variables
ph = 0
ph_adc_avg = None
tds_adc_avg = None
temp = None
ph_chart_points = []

try:
    with open("config/ph_cal_points.json", 'r') as read_file:
        ph_cal_points = json.load(read_file)

except Exception as e:
    print("Can't load ph calibration setting config, load default ", e)
    ph_cal_points = {}


def interpolate_ph(data):
    print("PH calibration points:", data)
    points = [(data[d]['adc'], data[d]['ph']) for d in data]
    print(points)
    _chart_points = linear_interpolation(points)
    print(_chart_points)
    return _chart_points


# define async functions here
async def test_extension():
    global ph_chart_points
    if ph_cal_points:
        ph_chart_points = interpolate_ph(ph_cal_points)

    # Web UI extensions also can be added to main web.py module
    @web.app.route('/ph')
    async def web_control(request):
        response = send_file("ph/static/ph.html", compressed=False,
                             file_extension="")
        response.set_cookie("Extension", json.dumps(extension_navbar))
        response.set_cookie("phCalPoints", json.dumps(ph_cal_points))
        return response

    @web.app.route('/ph-upload-points', methods=['POST'])
    async def ph_upload_points(request):
        data = request.json
        print("PH calibration points:", data)
        points = [(data[d]['adc'], data[d]['ph']) for d in data]
        if len(points) < 2:
            print("Not enought calibration points")
            return {}
        global ph_chart_points
        ph_chart_points = linear_interpolation(points)
        print(ph_chart_points)

        with open("config/ph_cal_points.json", 'w') as write_file:
            write_file.write(json.dumps(data))
        global ph_cal_points
        ph_cal_points = data

        return {}

    @web.app.route('/ph-sse')
    @with_sse
    async def ph_sse(request, sse):
        print("Got connection")
        try:
            while "eof" not in str(request.sock[0]):
                event = json.dumps({
                    "ph": ph,
                    "ph_adc": ph_adc_avg,
                    "temp": temp,
                    "tds_adc": tds_adc_avg
                })
                await sse.send(event)  # unnamed event
                await asyncio.sleep(1)
        except Exception as e:
            print(f"Error in SSE loop: {e}")
        print("SSE closed")

    @web.app.route('/ph-chart-sse')
    @with_sse
    async def ph_chart_sse(request, sse):
        print("Got connection")
        old_ph_chart_points = None
        try:
            while "eof" not in str(request.sock[0]):
                if old_ph_chart_points != ph_chart_points:
                    old_ph_chart_points = ph_chart_points.copy()
                    event = json.dumps({
                        "PhChartPoints": old_ph_chart_points,
                    })

                    print("send Ph Chart settigs")
                    await sse.send(event)  # unnamed event
                    await asyncio.sleep(1)
                else:
                    # print("No updates, skip")
                    await asyncio.sleep(1)
        except Exception as e:
            print(f"Error in SSE loop: {e}")
        print("SSE closed")


def calculate_average(values):
    # print(f"Calculete average, len: {len(values)}")
    if len(values) > 0:
        average = sum(values) / len(values)
        return round(average, 4)
    else:
        return None


async def read_temp():
    global temp
    # TODO add non-blocking temp sensor sampling
    temp = 25.5
    return True
    temp_sensors = ds_sensor.scan()
    print("Start Temp sensor sampling")
    temp_buffer = []

    while 1:
        for _ in range(5):
            # Temp
            if temp_sensors:
                ds_sensor.convert_temp()
                _temp = ds_sensor.read_temp(temp_sensors[0])
                temp_buffer.append(_temp)
            await asyncio.sleep(0.5)

        if temp_buffer:
            temp = calculate_average(temp_buffer)
            temp_buffer = []
            # print("Temp: ", temp)


async def read_sensors():
    global ph_adc_avg
    global tds_adc_avg

    print("Start PH and TDS sensor sampling")
    i2c = I2C(0, sda=Pin(8), scl=Pin(9))
    ads1115 = ADS1115(i2c, address=72, gain=1)
    print("<<<<<<<<<<<<")
    ph_adc_buffer = []
    tds_buffer = []
    while 1:
        print("ADS1115 read")
        for _ in range(5):
            # PH ADC
            #print(ads1115)
            _value = ads1115.read(0, 0)
            ph_adc = ads1115.raw_to_v(_value)
            ph_adc_buffer.append(ph_adc)
            #print("ADS1115 PH Result: ", ph_adc)

            # TDS ADC
            _value = ads1115.read(0, 3)
            tds_adc = ads1115.raw_to_v(_value)
            tds_buffer.append(tds_adc)
            #print("ADS1115 TDS Result: ", ph_adc)

            await asyncio.sleep(0.5)
        if ph_adc_buffer:
            ph_adc_avg = calculate_average(ph_adc_buffer)
            ph_adc_buffer = []
            # print("PH ADC: ", ph_adc_avg)
        if tds_buffer:
            tds_adc_avg = calculate_average(tds_buffer)
            tds_buffer = []
            # print("TDS: ", tds_adc_avg)


async def ph_sampling():
    global ph
    global ph_adc_avg
    global temp
    global ph_chart_points

    while not ph_adc_avg or not ph_chart_points:
        await asyncio.sleep(1)
    print("Start Ph sampling")
    _old_chart_points = ph_chart_points.copy()
    adc_array = [x[0] for x in _old_chart_points]
    ph_array = [x[1] for x in _old_chart_points]
    ph = np.interp(ph_adc_avg, adc_array, ph_array)
    print(f"ADC: {ph_adc_avg}, PH: {ph}")
    ph_buffer = []
    while 1:
        for _ in range(15):
            # PH
            ph_buffer.append(ph_adc_avg)
            await asyncio.sleep(1)
        print(ph_buffer)
        if ph_buffer:
            ph_avg = calculate_average(ph_buffer)
            ph_buffer = []
            print("PH ADC: ", ph_adc_avg)
            print("TDS: ", tds_adc_avg)
            print("Temp: ", temp)
            if _old_chart_points != ph_chart_points:
                _old_chart_points = ph_chart_points.copy()
                adc_array = [x[0] for x in ph_chart_points]
                ph_array = [x[1] for x in ph_chart_points]

            ph = np.interp(ph_avg, adc_array, ph_array)
            print(f"ADC: {ph_avg}, PH: {ph}")


# Define extension async tasks here
extension_tasks = [test_extension, read_sensors, read_temp, ph_sampling]

# Define navbar extension here
extension_navbar = [{"name": "PH", "link": "/ph"}]

if __name__ == "__main__":
    asyncio.run(read_sensors())
