import time
import subprocess
import re

# Path to the log file
log_file = "/home/carloslinares/temperature_log.txt"


# Function to get the temperature from lm-sensors
def get_temperature():
    try:
        # Run the `sensors` command
        result = subprocess.run(['sensors'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if result.returncode != 0:
            print(f"Error running sensors: {result.stderr}")
            return None

        # Regular expression to find temperature values
        temp_pattern = r"Core \d+: +\+?(\d+\.?\d*)°C"
        match = re.findall(temp_pattern, result.stdout)

        if match:
            # For simplicity, assuming we're logging the first core temperature
            return float(match[0])
        else:
            print("Temperature not found in sensors output.")
            return None

    except Exception as e:
        print(f"Error: {e}")
        return None


# Function to log temperature to a file
def log_temperature():
    while True:
        temp = get_temperature()

        if temp is not None:
            with open(log_file, "a") as f:
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"{timestamp} - Temperature: {temp}°C\n")

        # Wait for 10 seconds before running again
        time.sleep(10)


if __name__ == "__main__":
    log_temperature()