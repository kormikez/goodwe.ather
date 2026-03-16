#!/usr/bin/env python3
# Lightweight EMS helper script for GoodWe ET inverters.
# v0.1 kormik@16mar2026
import argparse
import asyncio
import logging
import math
from datetime import datetime

import goodwe
import requests

# defaults
DEFAULT_HOURS_AHEAD = 8
DEFAULT_MIN_SOC = 15
DEFAULT_MAX_SOC = 95
SEASONAL_BONUS_FACTOR = 50


class GoodWeather:
    @staticmethod
    def setup_logging(log_file: str | None):
        # Configure logger once at startup. Use file if given, otherwise log to STDOUT.
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        logger.handlers.clear()

        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        handler = logging.FileHandler(log_file) if log_file else logging.StreamHandler()
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        # Return shortcut function: log("msg %s", value)
        return logger.info

    @staticmethod
    def fetch_cloud_cover(lat, lon, hours):
        # Pull hourly cloud cover forecast from Open-Meteo for given location.
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&hourly=cloud_cover"
            "&timezone=auto"
        )

        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()

        times = data["hourly"]["time"]
        clouds = data["hourly"]["cloud_cover"]

        now = datetime.now().astimezone()
        rows = []

        # Keep only current/future points, then trim to requested horizon.
        for t, c in zip(times, clouds):
            dt = datetime.fromisoformat(t).astimezone(now.tzinfo)
            if dt >= now:
                rows.append({"time": dt, "cloud": float(c)})

        return rows[:hours]

    @staticmethod
    def compute_cloud_cover_score(forecast):
        if not forecast:
            raise RuntimeError("No forecast data")

        weights = []
        values = []

        # Weighted average where near-term hours matter more than later hours.
        for i, item in enumerate(forecast):
            weight = max(1.0, len(forecast) - i)
            weights.append(weight)
            values.append(item["cloud"])

        return sum(v * w for v, w in zip(values, weights)) / sum(weights)

    @staticmethod
    def daylight_factor(lat):
        now = datetime.now()
        day_of_year = now.timetuple().tm_yday
        lat_rad = math.radians(lat)

        # Approximate solar declination for current day of year.
        decl = math.radians(23.44 * math.sin(math.radians(360 / 365 * (day_of_year - 81))))
        cos_omega = -math.tan(lat_rad) * math.tan(decl)

        # Convert sunrise/sunset hour angle to daylight duration.
        if cos_omega >= 1:
            daylight_hours = 0
        elif cos_omega <= -1:
            daylight_hours = 24
        else:
            omega = math.acos(cos_omega)
            daylight_hours = 2 * omega * 24 / (2 * math.pi)

        # Normalize to expected max day length.
        max_daylight = 16.5
        factor = daylight_hours / max_daylight
        return max(0.2, min(1.0, factor))

    @staticmethod
    def cloud_to_soc(cloud_cover_score, min_soc, max_soc):
        # Map 0..100 cloud score linearly to min_soc..max_soc.
        cloud_cover_score = max(0.0, min(100.0, cloud_cover_score))
        soc = min_soc + (cloud_cover_score / 100.0) * (max_soc - min_soc)
        return round(soc)


async def main():
    parser = argparse.ArgumentParser(description="GoodWeather EMS controller")
    parser.add_argument("--inverter-ip", required=True, help="IP address of the GoodWe inverter")
    parser.add_argument("--log-file", help="File to log to (disables STDOUT)")
    parser.add_argument("--hours-ahead",type=int,default=DEFAULT_HOURS_AHEAD,
                        help="Hours ahead to consider for cloud coverage")
    parser.add_argument("--min-soc", type=int, default=DEFAULT_MIN_SOC, help="Minimum battery SOC%")
    parser.add_argument("--max-soc", type=int, default=DEFAULT_MAX_SOC, help="Maximum battery SOC%")
    parser.add_argument("--lat", type=float, help="Location latitude (e.g. 53.272)")
    parser.add_argument("--lon", type=float, help="Location longitude (e.g. 16.469)")
    parser.add_argument("--stop", action="store_true", help="Stop fast charging immediately")
    parser.add_argument("--dry-run",action="store_true", help="Do not write inverter settings")
    args = parser.parse_args()

    gw = GoodWeather()
    log = gw.setup_logging(args.log_file)

    log("Using inverter IP: %s", args.inverter_ip)
    if args.dry_run:
        log("Dry-run mode enabled: write_setting calls are skipped")

    inverter = await goodwe.connect(args.inverter_ip, family="ET")

    # Write guard: in dry-run, only log intended writes.
    async def write_setting(name: str, value: int):
        if args.dry_run:
            log("[DRY-RUN] Skipping write_setting(%s=%s)", name, value)
            return
        await inverter.write_setting(name, value)

    # Stop charge if requested.
    if args.stop:
        log("Stop requested: disabling fast charging")
        await write_setting("fast_charging", 0)
        return

    # Validate that coordinates are provided when not stopping.
    if args.lat is None or args.lon is None:
        parser.error("Please provide coordinates with --lat and --lon params")

    log("Config: hours=%d min_soc=%d max_soc=%d", args.hours_ahead, args.min_soc, args.max_soc)

    # Get cloud cover forecast for the next hours and compute a score.
    forecast = gw.fetch_cloud_cover(args.lat, args.lon, args.hours_ahead)

    log("Cloud cover forecast next %dh:", args.hours_ahead)
    for f in forecast:
        log("  %s -> %.0f%%", f["time"].strftime("%H:%M"), f["cloud"])

    cloud_cover_score = gw.compute_cloud_cover_score(forecast)
    light = gw.daylight_factor(args.lat)

    # Seasonal bonus increases target SOC during shorter-day periods.
    seasonal_bonus = (1.0 - light) * SEASONAL_BONUS_FACTOR
    effective_cloud = min(100.0, cloud_cover_score + seasonal_bonus)

    log("Cloud score: %.1f%%", cloud_cover_score)
    log("Daylight factor: %.2f", light)
    log("Seasonal bonus: %.1f%%", seasonal_bonus)
    log("Effective cloud score: %.1f%%", effective_cloud)

    # Map cloud score to target SOC.
    target_soc = gw.cloud_to_soc(effective_cloud, args.min_soc, args.max_soc)
    log("Target SOC: %d%%", target_soc)

    runtime = await inverter.read_runtime_data()
    current_soc = int(runtime["battery_soc"])
    log("Current SOC: %d%%", current_soc)

    # Get current target to avoid unnecessary updates.
    try:
        current_target = await inverter.read_setting("fast_charging_soc")
        log("Current fast_charging_soc: %s", current_target)
    except Exception:
        current_target = None
        log("Could not read fast_charging_soc")

    # If battery already reached target, ensure fast charging is off.
    if current_soc >= target_soc:
        log("SOC >= target -> disabling fast charging")
        await write_setting("fast_charging", 0)
        return

    # Update inverter target only when needed.
    if current_target is None or int(current_target) != target_soc:
        log("Setting fast_charging_soc to %d%%", target_soc)
        await write_setting("fast_charging_soc", target_soc)
    else:
        log("Target already set")

    # Enable fast charging to reach target.
    log("Turning on fast charging")
    await write_setting("fast_charging", 1)
    log("Charging towards %d%%", target_soc)


if __name__ == "__main__":
    asyncio.run(main())
