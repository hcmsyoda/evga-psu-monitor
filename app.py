#!/usr/bin/env python3
"""
EVGA SuperNOVA 850 PSU Monitor
Monitors system power draw, temperatures, and fan speeds via:
  - /sys/class/hwmon (motherboard INA219/INA3221 power sensors)
  - Intel RAPL (CPU package power)
  - NVIDIA SMI (GPU power)
  - lm-sensors (temperatures & fan RPMs)
"""

import os
import re
import json
import glob
import time
import subprocess
from pathlib import Path
from datetime import datetime

from flask import Flask, render_template, jsonify

app = Flask(__name__)

# Friendly names for common hwmon sensor labels
FRIENDLY_NAMES = {
    # NCT6793 / Nuvoton Super I/O
    "SYSTIN": "System Board",
    "CPUTIN": "CPU Socket",
    "AUXTIN0": "Aux Temp 0",
    "AUXTIN1": "Aux Temp 1",
    "AUXTIN2": "Aux Temp 2",
    "AUXTIN3": "Aux Temp 3",
    "TSI0_TEMP": "CPU (TSI)",
    "TSI1_TEMP": "CPU (TSI)",
    "TSI2_TEMP": "PCH / VRM",
    "TSI3_TEMP": "VRM 2",
    "TSI4_TEMP": "VRM 3",
    "TSI5_TEMP": "VRM 4",
    "TSI6_TEMP": "VRM 5",
    # ACPI
    "acpitz": "ACPI Thermal",
    "Sensor 1": "ACPI Sensor 1",
    "Sensor 2": "ACPI Sensor 2",
    # Coretemp
    "Package Id 0": "CPU Package",
    "Core 0": "CPU Core 0",
    "Core 1": "CPU Core 1",
    "Core 2": "CPU Core 2",
    "Core 3": "CPU Core 3",
    "Core 4": "CPU Core 4",
    "Core 5": "CPU Core 5",
    "Core 6": "CPU Core 6",
    "Core 7": "CPU Core 7",
    # PCH (Platform Controller Hub)
    "Pch Chip Temp": "PCH Chip",
    "Pch Cpu Temp": "PCH CPU Link",
    "Pch Mch Temp": "PCH Memory Hub",
    # PECI (Platform Environment Control Interface)
    "Peci Agent 0": "CPU PECI",
    "Peci Agent 0 Calibration": "CPU Calibration",
    # Fans
    "fan1": "Fan 1",
    "fan2": "Fan 2",
    "fan3": "Fan 3",
    "fan4": "Fan 4",
    "fan5": "Fan 5",
    "fan6": "Fan 6",
    # Voltages (NCT6793 standard mappings)
    "Vcore": "CPU Vcore",
    "AVCC": "AVCC (+3.3V)",
    "3VCC": "+3.3V",
    "+3.3V": "+3.3V",
    "+5V": "+5V",
    "+12V": "+12V",
    "VIN5": "VIN5",
    "VIN6": "VIN6",
    "3VSB": "3.3V Standby",
    "Vbat": "CMOS Battery",
    "VTT": "DRAM Termination",
    "VIN10": "VIN10",
    "VIN11": "VIN11",
    "VIN12": "VIN12",
    "VIN13": "VIN13",
    "VIN14": "VIN14",
}

def friendly_name(raw_label, chip_name, sensor_type, channel):
    """Return a human-readable sensor name."""
    # Direct lookup
    if raw_label in FRIENDLY_NAMES:
        return FRIENDLY_NAMES[raw_label]
    # Voltage channel mapping (NCT6793 standard)
    if sensor_type == "volt":
        volt_by_channel = {
            "0": "CPU Vcore", "1": "AVCC (+3.3V)", "2": "+3.3V",
            "3": "+5V", "4": "+12V", "5": "VIN5", "6": "VIN6",
            "7": "3.3V Standby", "8": "CMOS Battery", "9": "DRAM Termination",
            "10": "VIN10", "11": "VIN11", "12": "VIN12",
            "13": "VIN13", "14": "VIN14",
        }
        if str(channel) in volt_by_channel:
            return volt_by_channel[str(channel)]
    # Fan channel mapping
    if sensor_type == "fan":
        return f"Fan {int(channel) if channel.isdigit() else channel}"
    # Fallback: clean up the raw label
    clean = raw_label.replace("_", " ").title()
    if clean.startswith("Temp") or clean.startswith("Fan") or clean.startswith("In"):
        return f"{chip_name} {clean}"
    return clean

# ---------------------------------------------------------------------------
# Sensor reading helpers
# ---------------------------------------------------------------------------

def read_file(path):
    """Read a sysfs file, return stripped string or None."""
    try:
        return Path(path).read_text().strip()
    except (OSError, PermissionError):
        return None


def read_hwmon_sensors():
    """Walk /sys/class/hwmon and collect power, temp, fan, voltage, current."""
    sensors = []
    hwmon_base = Path("/sys/class/hwmon")
    if not hwmon_base.exists():
        return sensors

    for hwmon_dir in sorted(hwmon_base.iterdir()):
        name = read_file(hwmon_dir / "name") or hwmon_dir.name
        device_path = hwmon_dir

        # Power sensors (microwatts -> watts)
        for f in sorted(device_path.glob("power*_input")):
            ch = f.stem.replace("power", "").replace("_input", "")
            val_uw = read_file(f)
            if val_uw:
                try:
                    watts = int(val_uw) / 1_000_000
                    sensors.append({
                        "type": "power", "name": name,
                        "channel": ch or "0",
                        "value": round(watts, 2), "unit": "W"
                    })
                except ValueError:
                    pass

        # Temperature sensors (millidegrees -> celsius)
        for f in sorted(device_path.glob("temp*_input")):
            ch = f.stem.replace("temp", "").replace("_input", "")
            val_mc = read_file(f)
            if val_mc:
                try:
                    celsius = int(val_mc) / 1000
                    # Skip obviously invalid readings (disconnected sensors)
                    if celsius > 150 or celsius < -40:
                        continue
                    label = read_file(device_path / f"temp{ch}_label") or f"Sensor {ch}"
                    friendly = friendly_name(label, name, "temp", ch)
                    sensors.append({
                        "type": "temperature", "name": name,
                        "channel": ch, "label": friendly,
                        "raw_label": label,
                        "value": round(celsius, 1), "unit": "°C"
                    })
                except ValueError:
                    pass

        # Fan sensors (RPM)
        for f in sorted(device_path.glob("fan*_input")):
            ch = f.stem.replace("fan", "").replace("_input", "")
            val_rpm = read_file(f)
            if val_rpm:
                try:
                    rpm = int(val_rpm)
                    if rpm <= 0:
                        continue
                    label = read_file(device_path / f"fan{ch}_label") or f"fan{ch}"
                    friendly = friendly_name(label, name, "fan", ch)
                    sensors.append({
                        "type": "fan", "name": name,
                        "channel": ch, "label": friendly,
                        "value": rpm, "unit": "RPM"
                    })
                except ValueError:
                    pass

        # Voltage sensors (millivolts -> volts)
        for f in sorted(device_path.glob("in*_input")):
            ch = f.stem.replace("in", "").replace("_input", "")
            val_mv = read_file(f)
            if val_mv:
                try:
                    mv = int(val_mv)
                    volts = mv / 1000
                    # Skip obviously invalid voltages
                    if volts < 0 or volts > 20:
                        continue
                    label = read_file(device_path / f"in{ch}_label") or f"in{ch}"
                    friendly = friendly_name(label, name, "volt", ch)
                    sensors.append({
                        "type": "voltage", "name": name,
                        "channel": ch, "label": friendly,
                        "value": round(volts, 3), "unit": "V"
                    })
                except ValueError:
                    pass

        # Current sensors (milliamps -> amps)
        for f in sorted(device_path.glob("curr*_input")):
            ch = f.stem.replace("curr", "").replace("_input", "")
            val_ma = read_file(f)
            if val_ma:
                try:
                    amps = int(val_ma) / 1000
                    sensors.append({
                        "type": "current", "name": name,
                        "channel": ch, "value": round(amps, 3), "unit": "A"
                    })
                except ValueError:
                    pass

    return sensors


def read_rapl():
    """Read Intel RAPL CPU package power."""
    rapl_base = Path("/sys/class/powercap")
    results = []
    if not rapl_base.exists():
        return results

    for domain in rapl_base.glob("intel-rapl:*"):
        name_file = domain / "name"
        energy_file = domain / "energy_uj"
        max_file = domain / "max_energy_range_uj"
        if not name_file.exists() or not energy_file.exists():
            continue
        name = read_file(name_file)
        if not name:
            continue
        try:
            energy_uj = int(read_file(energy_file))
            max_uj = int(read_file(max_file)) if max_file.exists() else None
            results.append({
                "name": name, "energy_uj": energy_uj,
                "max_energy_uj": max_uj
            })
        except (ValueError, TypeError):
            pass
    return results


def read_nvidia_gpu():
    """Read GPU power/temp/fan via nvidia-smi."""
    try:
        out = subprocess.check_output(
            ["nvidia-smi",
             "--query-gpu=name,power.draw,temperature.gpu,fan.speed,clocks.gr,clocks.mem,utilization.gpu,utilization.memory,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            timeout=5, stderr=subprocess.DEVNULL
        ).decode().strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return []

    gpus = []
    for line in out.split("\n"):
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 10:
            gpus.append({
                "name": parts[0],
                "power_w": float(parts[1]) if parts[1] != "[N/A]" else None,
                "temp_c": float(parts[2]) if parts[2] != "[N/A]" else None,
                "fan_pct": float(parts[3]) if parts[3] != "[N/A]" else None,
                "clock_gr_mhz": float(parts[4]) if parts[4] != "[N/A]" else None,
                "clock_mem_mhz": float(parts[5]) if parts[5] != "[N/A]" else None,
                "util_gpu_pct": float(parts[6]) if parts[6] != "[N/A]" else None,
                "util_mem_pct": float(parts[7]) if parts[7] != "[N/A]" else None,
                "mem_used_mb": float(parts[8]) if parts[8] != "[N/A]" else None,
                "mem_total_mb": float(parts[9]) if parts[9] != "[N/A]" else None,
            })
    return gpus


def get_system_summary():
    """Aggregate all sensor data into a single dict."""
    hwmon = read_hwmon_sensors()
    rapl = read_rapl()
    gpus = read_nvidia_gpu()

    # Separate by type for the dashboard
    power_sensors = [s for s in hwmon if s["type"] == "power"]
    temp_sensors = [s for s in hwmon if s["type"] == "temperature"]
    fan_sensors = [s for s in hwmon if s["type"] == "fan"]
    voltage_sensors = [s for s in hwmon if s["type"] == "voltage"]
    current_sensors = [s for s in hwmon if s["type"] == "current"]

    # Estimate total system power
    total_power = sum(s["value"] for s in power_sensors)
    gpu_power = sum(g["power_w"] for g in gpus if g.get("power_w"))
    rapl_power = 0
    for r in rapl:
        if "package" in r["name"]:
            rapl_power = max(rapl_power, 0)  # RAPL is energy, not instant power

    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "power": {
            "sensors": power_sensors,
            "total_hwmon_w": round(total_power, 2),
            "gpu_total_w": round(gpu_power, 2),
        },
        "temperatures": temp_sensors,
        "fans": fan_sensors,
        "voltages": voltage_sensors,
        "currents": current_sensors,
        "gpus": gpus,
        "rapl": rapl,
    }


# ---------------------------------------------------------------------------
# Flask routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/sensors")
def api_sensors():
    return jsonify(get_system_summary())


@app.route("/api/health")
def api_health():
    return jsonify({"status": "ok", "timestamp": datetime.utcnow().isoformat()})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8088))
    debug = os.environ.get("DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
