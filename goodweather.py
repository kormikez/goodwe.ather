#!/usr/bin/env python3
# Lightweight EMS helper script for GoodWe ET inverters
# v0.2 kormik@20mar2026

import argparse
import asyncio
import logging
from datetime import datetime

import goodwe
import requests


# Default parameters
DEFAULT_HOURS_AHEAD = 6
DEFAULT_MIN_SOC = 15
DEFAULT_MAX_SOC = 95
DEFAULT_SKIP_HOURS = 2
DEFAULT_MAX_TRIES = 3
DEFAULT_RETRY_DELAY = 60


class GoodWeather:

    # Setup logging to file or STDOUT
    @staticmethod
    def setup_logging(log_file: str | None):
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        logger.handlers.clear()

        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        handler = logging.FileHandler(log_file) if log_file else logging.StreamHandler()
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        return logger.info

    # Get irradiance forecast and sunset time from Open-Meteo
    @staticmethod
    def get_forecast(lat, lon, hours):
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&hourly=shortwave_radiation"
            "&daily=sunset"
            "&timezone=auto"
        )

        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()

        times = data["hourly"]["time"]
        radiation = data["hourly"]["shortwave_radiation"]

        now = datetime.now().astimezone()
        rows = []

        for t, rad in zip(times, radiation):
            dt = datetime.fromisoformat(t).astimezone(now.tzinfo)
            if dt >= now:
                rows.append({"time": dt, "irr": float(rad)})

        # next sunset
        sunsets = [
            datetime.fromisoformat(t).astimezone(now.tzinfo)
            for t in data["daily"]["sunset"]
        ]

        next_sunset = None
        for s in sunsets:
            if s >= now:
                next_sunset = s
                break

        return rows[:hours], next_sunset

    # Compute average irradiance over selected hours
    @staticmethod
    def calculate_avg_irradiance(forecast):
        if not forecast:
            raise RuntimeError("No irradiance data")

        return sum(item["irr"] for item in forecast) / len(forecast)

    # Convert irradiance to desired SOC
    # More sun -> lower need to charge from grid
    @staticmethod
    def irradiance_to_soc(irr, min_soc, max_soc):
        irr = max(0.0, min(1000.0, irr))
        sun_factor = irr / 1000.0
        soc = max_soc - sun_factor * (max_soc - min_soc)
        return round(soc)

    # Increase target SOC as sunset approaches
    @staticmethod
    def sunset_proximity_boost(target_soc, max_soc, next_sunset):
        now = datetime.now().astimezone()

        # no sunset info or already dark
        if next_sunset is None or now >= next_sunset:
            return max_soc, 1.0, -1.0

        hours_to_sunset = (next_sunset - now).total_seconds() / 3600.0

        # no increase if plenty of daylight left
        if hours_to_sunset >= 4:
            sunset_boost_factor = 0.0

        # linear ramp during last 4 hours
        elif hours_to_sunset > 0:
            sunset_boost_factor = (4.0 - hours_to_sunset) / 4.0

        else:
            sunset_boost_factor = 1.0

        boosted_soc = round(target_soc + sunset_boost_factor * (max_soc - target_soc))

        return min(boosted_soc, max_soc), sunset_boost_factor, hours_to_sunset


# MAIN
async def main():
    parser = argparse.ArgumentParser(
        description="GoodWe.ather: TOU on steroids",
    )
    parser.add_argument(
        "--inverter-ip", required=True, help="IP address of the GoodWe inverter"
    )
    parser.add_argument(
        "--log-file",
        help="File to log to (disables STDOUT)",
    )
    parser.add_argument(
        "--hours-ahead",
        type=int,
        default=DEFAULT_HOURS_AHEAD,
        help="Hours ahead to consider for cloud coverage",
    )
    parser.add_argument(
        "--skip-hours",
        type=int,
        default=DEFAULT_SKIP_HOURS,
        help="Initial hours to skip (assume this time is consumed during charging)",
    )
    parser.add_argument(
        "--min-soc",
        type=int,
        default=DEFAULT_MIN_SOC,
        help="Minimum battery SOC%",
    )
    parser.add_argument(
        "--max-soc",
        type=int,
        default=DEFAULT_MAX_SOC,
        help="Maximum battery SOC%",
    )
    parser.add_argument(
        "--lat",
        type=float,
        help="Location latitude (e.g. 53.272)",
    )
    parser.add_argument(
        "--lon",
        type=float,
        help="Location longitude (e.g. 16.469)",
    )
    parser.add_argument(
        "--stop",
        action="store_true",
        help="Stop fast charging immediately",
    ),
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run - do not write inverter settings",
    )

    args = parser.parse_args()

    gw = GoodWeather()
    log = gw.setup_logging(args.log_file)

    log(f"Using inverter IP: {args.inverter_ip}")

    if args.dry_run:
        log("Dry-run mode enabled")

    inverter = await goodwe.connect(args.inverter_ip, family="ET")

    async def write_setting(name, value):
        if args.dry_run:
            log(f"[DRY-RUN] write_setting({name}={value})")
            return
        await inverter.write_setting(name, value)

    if args.stop:
        log("Stop requested: disabling fast charging")
        await write_setting("fast_charging", 0)
        return

    if args.lat is None or args.lon is None:
        parser.error("Please provide --lat and --lon")

    log(
        f"Config: hours={args.hours_ahead} skip_hours={args.skip_hours} min_soc={args.min_soc} max_soc={args.max_soc}",
    )

    # Get forecast
    forecast, next_sunset = gw.get_forecast(
        args.lat, args.lon, args.skip_hours + args.hours_ahead
    )

    log(f"Irradiance forecast next {args.hours_ahead}h:")
    for f in forecast[args.skip_hours :]:
        log(f"  {f['time'].strftime('%H:%M')} -> {f['irr']:.0f} W/sqm")

    if next_sunset:
        log(f"Next sunset: {next_sunset.strftime('%Y-%m-%d %H:%M')}")
    else:
        log("Next sunset: unavailable")

    # Compute target SOC based on irradiance and sunset proximity
    irradiance_score = gw.calculate_avg_irradiance(forecast[args.skip_hours :])

    irradiance_based_target_soc = gw.irradiance_to_soc(
        irradiance_score,
        args.min_soc,
        args.max_soc,
    )

    target_soc, sunset_boost_factor, hours_to_sunset = gw.sunset_proximity_boost(
        irradiance_based_target_soc,
        args.max_soc,
        next_sunset,
    )

    log(f"Average irradiance: {irradiance_score:.1f} W/sqm")
    log(f"Irradiance based target SOC: {irradiance_based_target_soc}%")

    if hours_to_sunset >= 0:
        log(f"Hours to sunset: {hours_to_sunset:.2f}")
        log(f"Sunset boost factor: {sunset_boost_factor:.2f}")

    log(f"Final target SOC: {target_soc}%")

    # Inverter state
    runtime = await inverter.read_runtime_data()
    current_soc = int(runtime["battery_soc"])

    log(f"Current SOC: {current_soc}%")

    try:
        current_target = await inverter.read_setting("fast_charging_soc")
        log(f"Current fast_charging_soc: {current_target}")
    except Exception:
        current_target = None
        log("Could not read fast_charging_soc")

    # Control logic
    if current_soc >= target_soc:
        log("SOC >= target -> disabling fast charging")
        await write_setting("fast_charging", 0)
        return

    if current_target is None or int(current_target) != target_soc:
        log(f"Setting fast_charging_soc to {target_soc}%")
        await write_setting("fast_charging_soc", target_soc)
    else:
        log("Target already set")

    log("Turning on fast charging")
    await write_setting("fast_charging", 1)

    log(f"Charging towards {target_soc}%")


if __name__ == "__main__":

    for attempt in range(1, DEFAULT_MAX_TRIES + 1):
        try:
            asyncio.run(main())
            break
        except Exception as e:
            logging.basicConfig(
                level=logging.ERROR, format="%(asctime)s [%(levelname)s] %(message)s"
            )
            logging.exception(f"Error (attempt {attempt}/{DEFAULT_MAX_TRIES}): {e}")

            if attempt >= DEFAULT_MAX_TRIES:
                raise

            logging.error(f"Retrying in {DEFAULT_RETRY_DELAY} seconds...")
            __import__("time").sleep(DEFAULT_RETRY_DELAY)
