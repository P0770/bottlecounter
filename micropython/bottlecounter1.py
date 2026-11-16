from machine import Pin
import time
import os

# ==============================
# CONFIGURATION PINS
# ==============================

SENSOR_PIN = 18
START_BTN_PIN = 19
RESET_BTN_PIN = 23

# ==============================
# PARAMETRES
# ==============================

MIN_DETECTION_TIME = 20
COOLDOWN_TIME = 200

BTN_DEBOUNCE_MS = 40
LONG_PRESS_TIME = 2000

EEPROM_FILE = "count.txt"

# ==============================
# STOCKAGE FLASH (remplace NVS)
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

print("Systeme initialise.")
print("Valeur sauvegardee =", saved_value)

# ==============================
# LOOP
# ==============================

while True:
    now = time.ticks_ms()

    # ----- START / STOP -----
    start_now = start_btn.value()

    if start_prev == 1 and start_now == 0:
        time.sleep_ms(BTN_DEBOUNCE_MS)
        if start_btn.value() == 0:
            counting_enabled = not counting_enabled
            print("Comptage =", "ON" if counting_enabled else "OFF")
            while start_btn.value() == 0:
                time.sleep_ms(5)

    start_prev = start_now

    # ----- RESET -----
    reset_now = reset_btn.value()

    if reset_prev == 1 and reset_now == 0:
        reset_press_t0 = now
        long_press_fired = False

    if reset_now == 0 and reset_press_t0 != 0:
        if (not long_press_fired and
            time.ticks_diff(now, reset_press_t0) >= LONG_PRESS_TIME):
            
            bottle_count = saved_value
            print("⏪ Recharge depuis flash ->", bottle_count)
            long_press_fired = True

    if reset_prev == 0 and reset_now == 1 and reset_press_t0 != 0:
        if not long_press_fired:
            saved_value = bottle_count
            save_to_flash(saved_value)
            bottle_count = 0
            print("🔁 Reset. Sauvegarde flash =", saved_value)

        reset_press_t0 = 0
        long_press_fired = False

    reset_prev = reset_now

    # ----- DETECTION -----
    if counting_enabled:
        sensor_value = sensor.value()
        object_detected = (sensor_value == 0)

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
                        print("🍾 Total =", bottle_count)
                    state = WAIT_RELEASE
            else:
                state = IDLE

        elif state == WAIT_RELEASE:
            if not object_detected:
                state = IDLE

    time.sleep_ms(2)