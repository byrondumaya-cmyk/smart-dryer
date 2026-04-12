import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
GPIO.setup(25, GPIO.IN, pull_up_down=GPIO.PUD_UP)

print('Testing Limit Switch on GPIO 25 (Press CTRL+C to quit)')
print('Unpressed should be 1 (HIGH). Pressed should be 0 (LOW).')

try:
    while True:
        val = GPIO.input(25)
        print(f'Switch state: {val}', end='\r')
        time.sleep(0.1)
except KeyboardInterrupt:
    GPIO.cleanup()
    print('
Done.')
