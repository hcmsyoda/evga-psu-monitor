# EVGA SuperNOVA 850 — PSU Monitor Docker

System power, temperature, and fan monitoring dashboard for Unraid.

## ⚠️ Important Note

The EVGA SuperNOVA 850 (G2/G3/P2/T2) **does not have a USB monitoring interface**. Unlike Corsair HXi/RMi PSUs, there's no internal microcontroller exposing sensors over USB HID. This container monitors power via your **motherboard's built-in INA219/INA3221 power sensors** on the 24-pin ATX connector, plus Intel RAPL and NVIDIA GPU sensors.

## What It Monitors

| Category | Source | What You Get |
|----------|--------|-------------|
| **Power** | Motherboard hwmon (INA sensors) | Total system power draw in watts |
| **Temperatures** | hwmon + nvidia-smi | CPU, motherboard, GPU temps |
| **Fans** | hwmon | All fan RPMs (CPU, case, GPU) |
| **Voltages** | hwmon | 12V, 5V, 3.3V rail voltages |
| **GPU** | nvidia-smi | Power, temp, fan, clocks, VRAM |

## Build & Run on Unraid

### Option 1: Docker CLI (Unraid terminal)

```bash
# Build
docker build -t evga-psu-monitor /path/to/evga-psu-monitor/

# Run
docker run -d \
  --name evga-psu-monitor \
  --restart unless-stopped \
  -p 8088:8088 \
  -v /sys/class/hwmon:/sys/class/hwmon:ro \
  -v /sys/class/powercap:/sys/class/powercap:ro \
  -v /sys/class/thermal:/sys/class/thermal:ro \
  evga-psu-monitor:latest
```

### Option 2: docker-compose

```bash
cd /path/to/evga-psu-monitor/
docker-compose up -d
```

### Option 3: Unraid Community Applications

Import `unraid-template.xml` as a custom template.

## Access

Open `http://<your-unraid-ip>:8088` in your browser.

The dashboard auto-refreshes every 3 seconds with live sensor data.

## Troubleshooting

**No power sensors showing?**
Your motherboard may not expose INA sensors via hwmon. Check on the host:
```bash
ls /sys/class/hwmon/
cat /sys/class/hwmon/hwmon*/name
cat /sys/class/hwmon/hwmon*/power*_input
```

**No temperature data?**
```bash
sensors-detect  # run on host first
sensors
```

**Want NVIDIA GPU monitoring?**
Make sure `nvidia-smi` works on the host. The container runs it via subprocess.

## Files

```
evga-psu-monitor/
├── Dockerfile
├── docker-compose.yml
├── unraid-template.xml
├── requirements.txt
├── app.py              # Flask backend — reads hwmon/RAPL/nvidia-smi
├── templates/
│   └── index.html      # Dashboard HTML
└── static/
    ├── style.css       # Dark theme styling
    └── app.js          # Auto-refreshing sensor display
```
