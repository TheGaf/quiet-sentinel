import json
import shutil
import time
import urllib.request

URL = "http://127.0.0.1:8765/api/observe"

def cpu_counters():
    with open("/proc/stat") as f:
        fields = list(map(int, f.readline().split()[1:]))
    return sum(fields), fields[3] + fields[4]

def memory_percent():
    with open("/proc/meminfo") as f:
        info = {}
        for line in f:
            key, value = line.split(":", 1)
            info[key] = int(value.strip().split()[0])
    return 100 * (1 - info["MemAvailable"] / info["MemTotal"])

def send(metric, value):
    data = json.dumps({
        "host": "gafcloud",
        "metric": metric,
        "value": round(value, 2)
    }).encode()
    request = urllib.request.Request(
        URL, data=data,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        result = json.load(response)
    print(f"{metric}: {value:.1f}% — {result['state']}", flush=True)

print("Monitoring GafCloud every 30 seconds. Ctrl+C to stop.", flush=True)

previous = cpu_counters()
while True:
    time.sleep(30)
    current = cpu_counters()
    total = current[0] - previous[0]
    idle = current[1] - previous[1]
    previous = current
    cpu = 100 * (1 - idle / total) if total else 0

    try:
        send("cpu_percent", cpu)
        send("memory_percent", memory_percent())
        disk = shutil.disk_usage("/")
        send("disk_percent", 100 * disk.used / disk.total)
    except (OSError, ValueError, KeyError) as error:
        print(f"Collection error: {error}", flush=True)
