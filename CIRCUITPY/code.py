import alarm.pin
import alarm.time
import time
import storage
import board
import alarm
import adafruit_scd4x
import displayio
import digitalio
import ipaddress
import ssl
import wifi
import socketpool
import adafruit_requests
from adafruit_magtag.magtag import MagTag
from adafruit_io.adafruit_io import IO_HTTP, AdafruitIO_RequestError
import busio
from digitalio import DigitalInOut
import adafruit_esp32spi.adafruit_esp32spi_socket as socket
from adafruit_esp32spi import adafruit_esp32spi
from adafruit_display_text import label
from adafruit_bitmap_font import bitmap_font

try:
    from config import config
except ImportError:
    print("Device preferences are kept in config.py which is missing. Please set it up.")
    raise

try:
    from secrets import secrets
except ImportError:
    print("WiFi and other config details are kept in secrets.py which is missing.  Please set it up.")
    raise

wifi_enabled=False
wifi_good=False

unit_designation = config['unit_designation']
elevation = config['elevation']
barometric_pressure = config['barometric_pressure']
calibration_ppm = config['calibration_ppm']
sleep_interval = config['sleep_interval']
alarm_threshold = config['alarm_threshold']
warn_threshold = config['warn_threshold']
temperature_offset = config['temperature_offset']
significant_change = config['significant_change']
power_saving_light_level = config['power_saving_light_level']
power_saving_sleep_interval = config['power_saving_sleep_interval']
helpful_url = config['helpful_url']

magtag = MagTag() # screen size is 296 x 128
font_file = "MontserratDigits-53.pcf" # Google font.  Just numbers.

# a few of the following are not in use
magtag.add_text(
    text_font=font_file,
    text_position=(
       147,48
    ),
    text_scale=1,
    is_data=False
)

magtag.add_text(
    text_position=(
        280,
        120,
    ),
    text_scale=0.5,
    is_data=False,
)

magtag.add_text(
    text_position=(
        240,
        100,
    ),
    text_scale=1,
    is_data=False,
)

magtag.add_text(
    text_position=(
        140,
        115,
    ),
    text_scale=1,
    is_data=False,
)

#menu
magtag.add_text(
    text_position=(
        30,
        20,
    ),
    text_scale=1.5,
    is_data=False,
)

magtag.add_text(
    text_position=(
        30,
        50,
    ),
    text_scale=1,
    is_data=False,
)

magtag.add_text(
    text_position=(
        40,
        80,
    ),
    text_scale=1,
    is_data=False,
)

#short numbers
magtag.add_text(
    text_font=font_file,
    text_position=(
       164,48
    ),
    text_scale=1,
    is_data=False
)

# wakes up with no context other than what is stored in alarm.sleep_memory
if alarm.sleep_memory:
    previous_c02 = alarm.sleep_memory[5] | alarm.sleep_memory[6] << 8

i2c = board.I2C()
scd4x = adafruit_scd4x.SCD4X(i2c)

magtag.peripherals.neopixel_disable=True
magtag.peripherals.speaker_disable=True
print("Serial number:", [hex(i) for i in scd4x.serial_number])

if (alarm.wake_alarm is None):
    print("Nobody asleep here!")
if type(alarm.wake_alarm) is alarm.pin.PinAlarm:
    print("Somebody touched me.")
    magtag.peripherals.speaker_disable=False
    magtag.graphics.qrcode(helpful_url,qr_size=3, x=180, y=3)    
    magtag.graphics.set_background("menu.bmp")
    magtag.set_text("",4,True)
    while True:
        for i, b in enumerate(magtag.peripherals.buttons):
            if not b.value:
                print("Button %c pressed" % chr((ord("A") + i)))
                magtag.peripherals.play_tone(200, 0.07)

                if magtag.peripherals.button_b_pressed:
                    magtag.graphics.set_background("0xFFFFFF")
                    magtag.peripherals.speaker_disable=True
                    magtag.set_text("",4,False)
                    magtag.set_text("",6,False)
                    magtag.set_text("5 min. equalization...",5,True)
                    scd4x.start_periodic_measurement()
                    time.sleep(300);
                    magtag.set_text("Stopping sensor",5,True)
                    scd4x.stop_periodic_measurement()
                    time.sleep(0.6)
                    scd4x.temperature_offset=temperature_offset
                    scd4x.altitude = int(elevation)
                    scd4x.ambient_pressure = barometric_pressure
                    time.sleep(3)
                    magtag.set_text("Calibrating...",5,True)
                    result=scd4x.force_calibration(calibration_ppm)
                    time.sleep(10);
                    scd4x.persist_settings()
                    time.sleep(10);
                    magtag.set_text(result,5,False)
                    magtag.set_text("Done! Press 1st button to exit",6,True)

                if magtag.peripherals.button_a_pressed:
                    magtag.peripherals.speaker_disable=True
                    magtag.set_text("",4,False)
                    magtag.set_text("",5,False)
                    magtag.set_text("Exiting...",6,True)
                    previous_c02 = 0 # this will force a refresh
                    alarm.sleep_memory[6] = previous_c02 >> 8
                    alarm.sleep_memory[5] = previous_c02 & 255
                    # take a very short sleep and wake up newly calibrated
                    time_alarm = alarm.time.TimeAlarm(monotonic_time=time.monotonic() + 3)
                    alarm.exit_and_deep_sleep_until_alarms(time_alarm)
                time.sleep(.1)
                break
        else:
            time.sleep(0.01)

# It is required to deinit() the buttons in order to use them later as wakeup alarms.
# By default the MagTag grabs them for general user interaction use, which precludes
# their use for alarms
magtag.peripherals.buttons[0].deinit()
magtag.peripherals.buttons[1].deinit()

magtag.set_text("",3,False)
print("Temp offset: ", scd4x.temperature_offset)
print("Elevation: ", scd4x.altitude)
scd4x.start_low_periodic_measurement() # takes time but low power
print("Waiting for first measurement....")
time.sleep(1)
magtag.set_text("",6,False)
if alarm.sleep_memory:
    previous_c02 = alarm.sleep_memory[5] | alarm.sleep_memory[6] << 8
co2=0

for i in range(1):  # at one time I did a few warmup readings. Now just one and done
    while not scd4x.data_ready:
        time.sleep(0.25)
    print("Reading #%d" % i)
    print("CO2: %d ppm" % scd4x.CO2)
    co2=scd4x.CO2
    print("Temperature: %0.1f *C" % scd4x.temperature)
    print("Humidity: %0.1f %%" % scd4x.relative_humidity)
    print("Lux: %0.1f" % magtag.peripherals.light)
    print()

significant_co2 = significant_change * round(co2/significant_change)
magtag.set_text("",3,False)

if secrets["ssid"]:
    print("My MAC addr:", [hex(i) for i in wifi.radio.mac_address])
    print("Connecting to %s"%secrets["ssid"])
    try:
        wifi.radio.connect(secrets["ssid"], secrets["password"])
        print("Connected to %s!"%secrets["ssid"])
        print("My IP address is", wifi.radio.ipv4_address)

        ipv4 = ipaddress.ip_address("8.8.4.4")

        ADAFRUIT_IO_USER = secrets['aio_username']
        ADAFRUIT_IO_KEY = secrets['aio_key']

        pool = socketpool.SocketPool(wifi.radio)
        requests = adafruit_requests.Session(pool, ssl.create_default_context())

        io = IO_HTTP(ADAFRUIT_IO_USER, ADAFRUIT_IO_KEY, requests)
        
        # Go to the Adafruit IO website to create your feeds first.
        temperature_feed = io.get_feed(unit_designation.lower() + '-temperature')
        co2_feed = io.get_feed(unit_designation.lower() + '-co2')
        battery_feed = io.get_feed(unit_designation.lower() + '-battery')

        io.send_data(battery_feed['key'], magtag.peripherals.battery)
        io.send_data(temperature_feed['key'], ((scd4x.temperature*1.8)+32), precision=2) # Fahrenheit
        io.send_data(co2_feed['key'], co2)
    except:
        print("Wifi no good!");
        magtag.set_text("wifi fail",3,False)
        pass

low_charge = False
low_light = False
if magtag.peripherals.light < power_saving_light_level:
    print(magtag.peripherals.light)
    print(power_saving_light_level)
    low_light = True
    magtag.set_text("night mode",3,False)
if magtag.peripherals.battery < 3.65:
    low_charge = True
    magtag.set_text("charge battery ASAP",3,False)

if (abs(previous_c02 - significant_co2) >= significant_change):
    magtag.graphics.set_background("bg_normal.bmp")
    if (significant_co2 > warn_threshold):
        magtag.graphics.set_background("bg_warn.bmp")
    if (significant_co2 > alarm_threshold):
        magtag.graphics.set_background("bg_alarm.bmp")
    if (significant_co2 < 1000): # just some manual positioning of 3 digit numbers 
        magtag.set_text("",0,False)
        magtag.set_text("%d" % significant_co2,7,False)
    else:
        magtag.set_text("%d" % significant_co2,0,False)
        magtag.set_text("",7,False)
    magtag.set_text("{:+.2f}v".format(magtag.peripherals.battery),2,True)
    time.sleep(2)
    previous_c02 = significant_co2
else:
    print("Insufficient delta for refresh")

# store the current CO2 ppm for later use.  Sleep makes everything else go away
alarm.sleep_memory[6] = previous_c02 >> 8
alarm.sleep_memory[5] = previous_c02 & 255

# setup alarms and go to sleep
time_alarm = alarm.time.TimeAlarm(monotonic_time=time.monotonic() + sleep_interval)

if low_light or low_charge: # battery stretcher
    time_alarm = alarm.time.TimeAlarm(monotonic_time=time.monotonic() + power_saving_sleep_interval)

a_alarm = alarm.pin.PinAlarm(pin=board.BUTTON_A, value=False, pull=True)
b_alarm = alarm.pin.PinAlarm(pin=board.BUTTON_B, value=False, pull=True)

alarm.exit_and_deep_sleep_until_alarms(time_alarm,a_alarm,b_alarm)
