# goodwe.ather

Lightweight EMS helper script for GoodWe ET inverters.

It uses `fast_charging` feature of the inverter to charge battery based Solar Irradiance forecast for a given location.

It is configurable in terms of expected SOC%, as well as weather forecast time window.

The script must run locally as it connects to the inverter directly. It is not SEMS-dependent. It's meant to be run via cron during low tariff. Ideally put it on your Raspberry Pi or NAS device.

---

## Usage

```bash
python3 goodweather.py --inverter-ip 192.168.0.123 --lat 53.272 --lon 16.469
```

### Options

- `--inverter-ip`: The IP of your GoodWe device (default: unset)
- `--lat`, `--lon`: Coordinates of your location (default: unset)
- `--hours-ahead`:  Hours ahead to consider for cloud coverage (default: `6`)
- `--skip-hours`:  Initial hours to skip (assume this time is consumed during charging; default: `2`)
- `--min-soc`: Minimum charge % (default: `15`)
- `--max-soc`: Maximum charge % (default: `95`)
- `--log-file`: Write logs to file instead of stdout (default: unset)
- `--stop`: Immediately stop fast charging (default: `False`)
- `--dry-run`: Allows testing your settings; skips all inverter writes (default: `False`)

### Examples

Run in dry-run mode:

```bash
python3 goodweather.py --inverter-ip 192.168.0.123 --lat 52.380 --lon 16.835 \
    --max-soc 90 --dry-run
```

Stop charging now:

```bash
python3 goodweather.py --inverter-ip 192.168.0.123 --stop
```

Note: _You can use [find_inverter.py](helpers/find_inverter.py) helper script to get IP of your inverter (although it only works on Linux)._

---

## Cron example

Charge daily during the low tariff periods — 4:00–6:00 AM and 1:00–3:00 PM

```cron
0 4,13 * * * /opt/goodwe.ather/goodweather.py --inverter-ip 192.168.0.123 --lat 52.38 --lon 16.83 --log-file /var/log/goodweather.log
0 6,15 * * * /opt/goodwe.ather/goodweather.py --inverter-ip 192.168.0.123 --stop
```

### Example run results:
```
python3 goodweather.py --inverter-ip *** --lat 52.38 --lon 16.83 --max-soc 50
2026-03-19 04:00:05,973 [INFO] Using inverter IP: ***
2026-03-19 04:00:05,973 [INFO] Dry-run mode enabled
2026-03-19 04:00:06,530 [INFO] Config: hours=6 skip_hours=2 min_soc=15 max_soc=50
2026-03-19 04:00:06,686 [INFO] Irradiance forecast next 6h:
2026-03-19 04:00:06,686 [INFO]   07:00 -> 234 W/sqm
2026-03-19 04:00:06,687 [INFO]   08:00 -> 255 W/sqm
2026-03-19 04:00:06,687 [INFO]   09:00 -> 276 W/sqm
2026-03-19 04:00:06,687 [INFO]   10:00 -> 230 W/sqm
2026-03-19 04:00:06,688 [INFO]   11:00 -> 156 W/sqm
2026-03-19 04:00:06,688 [INFO]   12:00 -> 114 W/sqm
2026-03-19 04:00:06,688 [INFO] Next sunset: 2026-03-19 18:05
2026-03-19 04:00:06,689 [INFO] Average irradiance: 210.9 W/sqm
2026-03-19 04:00:06,689 [INFO] Irradiance based target SOC: 43%
2026-03-19 04:00:06,689 [INFO] Hours to sunset: 9.19
2026-03-19 04:00:06,689 [INFO] Sunset boost factor: 0.00
2026-03-19 04:00:06,690 [INFO] Final target SOC: 43%
2026-03-19 04:00:07,416 [INFO] Current SOC: 19%
2026-03-19 04:00:07,575 [INFO] Current fast_charging_soc: 66
2026-03-19 04:00:07,575 [INFO] Setting fast_charging_soc to 43%
2026-03-19 04:00:07,576 [INFO] Turning on fast charging
2026-03-19 04:00:07,576 [INFO] Charging towards 43%
```

```
python3 goodweather.py --inverter-ip *** --lat 28.12 --lon -15.43 --max-soc 100 --dry-run --skip-hours 5
2026-03-20 09:05:16,233 [INFO] Using inverter IP: ***
2026-03-20 09:05:16,233 [INFO] Dry-run mode enabled
2026-03-20 09:05:17,604 [INFO] Config: hours=6 skip_hours=5 min_soc=15 max_soc=100
2026-03-20 09:05:17,732 [INFO] Irradiance forecast next 6h:
2026-03-20 09:05:17,732 [INFO]   15:00 -> 886 W/sqm
2026-03-20 09:05:17,733 [INFO]   16:00 -> 758 W/sqm
2026-03-20 09:05:17,733 [INFO]   17:00 -> 571 W/sqm
2026-03-20 09:05:17,733 [INFO]   18:00 -> 343 W/sqm
2026-03-20 09:05:17,734 [INFO]   19:00 -> 110 W/sqm
2026-03-20 09:05:17,734 [INFO]   20:00 -> 2 W/sqm
2026-03-20 09:05:17,734 [INFO] Next sunset: 2026-03-20 19:13
2026-03-20 09:05:17,735 [INFO] Average irradiance: 444.9 W/sqm
2026-03-20 09:05:17,735 [INFO] Irradiance based target SOC: 62%
2026-03-20 09:05:17,735 [INFO] Hours to sunset: 10.13
2026-03-20 09:05:17,736 [INFO] Sunset boost factor: 0.00
2026-03-20 09:05:17,736 [INFO] Final target SOC: 62%
2026-03-20 09:05:18,488 [INFO] Current SOC: 16%
2026-03-20 09:05:18,645 [INFO] Current fast_charging_soc: 45
2026-03-20 09:05:18,645 [INFO] Setting fast_charging_soc to 62%
2026-03-20 09:05:18,646 [INFO] [DRY-RUN] write_setting(fast_charging_soc=62)
2026-03-20 09:05:18,646 [INFO] Turning on fast charging
2026-03-20 09:05:18,647 [INFO] [DRY-RUN] write_setting(fast_charging=1)
2026-03-20 09:05:18,647 [INFO] Charging towards 62%
```

---

## Notes

- You can run this script along with your regular GoodWe TOU feature. The `fast_charging` overrides it when it's on. Once off, inverter relies on TOU settings. You can use it to just boost your charging during bad weather while keeping some minimal settings for sunny summer days.
- The `fast_charging` feature does not have configurable instantaneous power limit. Consider setting global `max_charge_power` to prevent excessive consumption.
