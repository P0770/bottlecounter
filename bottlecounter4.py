from machine import Pin, I2C
import time
import os
import ssd1306
import framebuf

# ==============================
# CONFIGURATION PINS
# ==============================

SENSOR_PIN = 18
START_BTN_PIN = 19
RESET_BTN_PIN = 23

LED_GREEN_PIN = 25
LED_RED_PIN = 26

# ==============================
# OLED
# ==============================

i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)
oled = ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)
# ===== LOADING SCREEN =====
def show_loading():
    oled.fill(0)
    oled.text("Abbet-vins", 26, 28, 1)
    oled.rect(23, 23, 85, 18, 1)
    oled.show()
    time.sleep(3)
    oled.fill(0)
    oled.show()
    
show_loading()
# ==============================
# LED
# ==============================

led_green = Pin(LED_GREEN_PIN, Pin.OUT)
led_red = Pin(LED_RED_PIN, Pin.OUT)

def update_leds():
    if counting_enabled:
        led_green.value(1)
        led_red.value(0)
    else:
        led_green.value(0)
        led_red.value(1)

# ==============================
# PARAMETRES
# ==============================

MIN_DETECTION_TIME = 20
COOLDOWN_TIME = 200
BTN_DEBOUNCE_MS = 40
LONG_PRESS_TIME = 2000
EEPROM_FILE = "count.txt"

# ==============================
# FLASH
# ==============================

def save_to_flash(value):
    with open(EEPROM_FILE, "w") as f:
        f.write(str(value))

def load_from_flash():
    try:
        with open(EEPROM_FILE, "r") as f:
            return int(f.read())
    except:
        return 0

# ==============================
# BIG FONT x3
# ==============================

def draw_big_text(text, x, y, scale=3):
    for i, char in enumerate(text):
        buf = bytearray(8*8//8)
        fbuf = framebuf.FrameBuffer(buf, 8, 8, framebuf.MONO_VLSB)
        fbuf.text(char, 0, 0, 1)
        for px in range(8):
            for py in range(8):
                if fbuf.pixel(px, py):
                    oled.fill_rect(
                        x + i*8*scale + px*scale,
                        y + py*scale,
                        scale,
                        scale,
                        1
                    )

# ==============================
# AFFICHAGE
# ==============================

def update_display():
    oled.fill(0)

    oled.text("Bouteille", 0, 0)

    s = str(bottle_count)
    scale = 3
    width = len(s)*8*scale
    x = (128 - width)//2
    draw_big_text(s, x, 20, scale)

    oled.text("RUN" if counting_enabled else "STOP", 0, 55)

    oled.show()

# ==============================
# MACHINE D'ÉTAT
# ==============================

IDLE = 0
DETECTING = 1
WAIT_RELEASE = 2
state = IDLE

sensor = Pin(SENSOR_PIN, Pin.IN)
start_btn = Pin(START_BTN_PIN, Pin.IN, Pin.PULL_UP)
reset_btn = Pin(RESET_BTN_PIN, Pin.IN, Pin.PULL_UP)

bottle_count = 0
saved_value = load_from_flash()
counting_enabled = False

detect_start_time = 0
last_count_time = 0

start_prev = 1
reset_prev = 1
reset_press_t0 = 0
long_press_fired = False

object_detected = False

update_display()
update_leds()

# ==============================
# LOOP
# ==============================

while True:
    now = time.ticks_ms()

    # START
    start_now = start_btn.value()
    if start_prev == 1 and start_now == 0:
        time.sleep_ms(BTN_DEBOUNCE_MS)
        if start_btn.value() == 0:
            counting_enabled = not counting_enabled
            update_display()
            update_leds()
            while start_btn.value() == 0:
                time.sleep_ms(5)
    start_prev = start_now

    # RESET
    reset_now = reset_btn.value()
    if reset_prev == 1 and reset_now == 0:
        reset_press_t0 = now
        long_press_fired = False

    if reset_now == 0 and reset_press_t0 != 0:
        if (not long_press_fired and
            time.ticks_diff(now, reset_press_t0) >= LONG_PRESS_TIME):
            bottle_count = saved_value
            long_press_fired = True
            update_display()

    if reset_prev == 0 and reset_now == 1 and reset_press_t0 != 0:
        if not long_press_fired:
            saved_value = bottle_count
            save_to_flash(saved_value)
            bottle_count = 0
            update_display()
        reset_press_t0 = 0

    reset_prev = reset_now

    # DETECTION
    sensor_value = sensor.value()

    if counting_enabled:
        object_detected = (sensor_value == 0)
    else:
        object_detected = False
        
# indicateur carré
    if sensor_value == 0:
        oled.fill_rect(90, 30, 40, 30, 1)
    else:
        oled.fill_rect(90, 30, 40, 30, 0)
    oled.show()
    if counting_enabled:
        if state == IDLE:
            if object_detected:
                detect_start_time = now
                state = DETECTING

        elif state == DETECTING:
            if object_detected:
                if time.ticks_diff(now, detect_start_time) >= MIN_DETECTION_TIME:
                    if time.ticks_diff(now, last_count_time) >= COOLDOWN_TIME:
                        bottle_count += 1
                        last_count_time = now
                        update_display()
                    state = WAIT_RELEASE
            else:
                state = IDLE

        elif state == WAIT_RELEASE:
            if not object_detected:
                state = IDLE

    time.sleep_ms(5)