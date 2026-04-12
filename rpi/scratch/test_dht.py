import time
import board
import adafruit_dht

# --- CONFIGURATION ---
# Change these two variables to match the sensor you want to test!
PIN_NUMBER = 4       # GPIO number (e.g., 4 for Slot 1)
SENSOR_MODEL = "22"  # "22" for DHT22/AM2302, "11" for DHT11

def test_sensor():
    print(f"--- Hardware Test: DHT{SENSOR_MODEL} on GPIO{PIN_NUMBER} ---")
    
    pin = getattr(board, f"D{PIN_NUMBER}")
    if SENSOR_MODEL == "22":
        dht_device = adafruit_dht.DHT22(pin, use_pulseio=False)
    else:
        dht_device = adafruit_dht.DHT11(pin, use_pulseio=False)

    print("Checking sensor data (will try 5 times)...")
    
    for i in range(5):
        try:
            temp_c = dht_device.temperature
            humidity = dht_device.humidity
            print(f"[{i+1}] Success! Temp: {temp_c:.1f} C, Humidity: {humidity}%")
        except RuntimeError as error:
            # Common errors are 'Checksum did not validate' or 'Timed out'
            print(f"[{i+1}] Reading error: {error.args[0]}")
        except Exception as error:
            dht_device.exit()
            raise error

        time.sleep(2.0)
    
    dht_device.exit()
    print("--- Test Complete ---")

if __name__ == "__main__":
    test_sensor()
