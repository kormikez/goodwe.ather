# goodwe.ather

Lightweight EMS helper script for GoodWe ET inverters.

It uses `fast_charging` feature of the inverter to charge battery based on:
- cloud coverate forecast from open-meteo.com for given location
- season/daylight factor

It is configurable in terms of expected SOC%, as well as weather forecast time window.

The script must run locally as it connects to the inverter directly. It is not SEMS-dependent. It's meant to be run via cron during low tariff. Ideally put it on your Raspberry Pi or NAS device.

---

## Usage

```bash
python3 goodweather.py --inverter-ip 192.168.0.123 --lat 53.272 --lon 16.469
```

### Options

- `--inverter-ip`: The IP of your GoodWe device
- `--lat`, `--lon`: Coordinates of your location
- `--hours-ahead`: Hours ahead to consider for cloud coverage
- `--min-soc` Minimum charge %
- `--max-soc` Maximum charge %
- `--log-file`: Write logs to file instead of stdout
- `--stop` Immediately stop fast charging
- `--dry-run` Allows testing your settings; skips all inverter writes

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
python3 goodweather.py --inverter-ip 192.168.88.177 --lat 52.38 --lon 16.83 --max-soc 90
2026-03-15 04:00:05,653 [INFO] Using inverter IP: ***
2026-03-15 04:00:06,210 [INFO] Config: hours=8 min_soc=15 max_soc=90
2026-03-15 04:00:06,359 [INFO] Cloud cover forecast next 8h:
2026-03-15 04:00:06,360 [INFO]   05:00 -> 100%
2026-03-15 04:00:06,360 [INFO]   06:00 -> 100%
2026-03-15 04:00:06,360 [INFO]   07:00 -> 98%
2026-03-15 04:00:06,361 [INFO]   08:00 -> 73%
2026-03-15 04:00:06,361 [INFO]   09:00 -> 100%
2026-03-15 04:00:06,361 [INFO]   10:00 -> 100%
2026-03-15 04:00:06,362 [INFO]   11:00 -> 100%
2026-03-15 04:00:06,362 [INFO]   12:00 -> 98%
2026-03-15 04:00:06,362 [INFO] Cloud score: 95.9%
2026-03-15 04:00:06,363 [INFO] Daylight factor: 0.70
2026-03-15 04:00:06,363 [INFO] Seasonal bonus: 14.9%
2026-03-15 04:00:06,363 [INFO] Effective cloud score: 100.0%
2026-03-15 04:00:06,364 [INFO] Target SOC: 90%
2026-03-15 04:00:09,069 [INFO] Current SOC: 23%
2026-03-15 04:00:09,227 [INFO] Current fast_charging_soc: 95
2026-03-15 04:00:09,228 [INFO] Setting fast_charging_soc to 90%
2026-03-15 04:00:09,228 [INFO] Turning on fast charging
2026-03-15 04:00:09,229 [INFO] Charging towards 90%
```

```
python3 goodweather.py --inverter-ip *** --lat 51.25 --lon 22.57 --dry-run
2026-03-16 10:15:32,334 [INFO] Using inverter IP: ***
2026-03-16 10:15:32,335 [INFO] Dry-run mode enabled: write_setting calls are skipped
2026-03-16 10:15:32,887 [INFO] Config: hours=8 min_soc=15 max_soc=95
2026-03-16 10:15:33,031 [INFO] Cloud cover forecast next 8h:
2026-03-16 10:15:33,032 [INFO]   11:00 -> 0%
2026-03-16 10:15:33,032 [INFO]   12:00 -> 0%
2026-03-16 10:15:33,033 [INFO]   13:00 -> 0%
2026-03-16 10:15:33,033 [INFO]   14:00 -> 0%
2026-03-16 10:15:33,033 [INFO]   15:00 -> 33%
2026-03-16 10:15:33,034 [INFO]   16:00 -> 30%
2026-03-16 10:15:33,034 [INFO]   17:00 -> 2%
2026-03-16 10:15:33,034 [INFO]   18:00 -> 0%
2026-03-16 10:15:33,035 [INFO] Cloud score: 6.3%
2026-03-16 10:15:33,035 [INFO] Daylight factor: 0.70
2026-03-16 10:15:33,035 [INFO] Seasonal bonus: 14.9%
2026-03-16 10:15:33,036 [INFO] Effective cloud score: 21.1%
2026-03-16 10:15:33,036 [INFO] Target SOC: 32%
2026-03-16 10:15:34,055 [INFO] Current SOC: 78%
2026-03-16 10:15:34,215 [INFO] Current fast_charging_soc: 95
2026-03-16 10:15:34,215 [INFO] SOC >= target -> disabling fast charging
2026-03-16 10:15:34,215 [INFO] [DRY-RUN] Skipping write_setting(fast_charging=0)
```

---

## Notes

- You can run this script along with your regular GoodWe TOU feature. The `fast_charging` overrides it when it's on. Once off, inverter relies on TOU settings. You can use it to just boost your charging during bad weather while keeping some minimal settings for sunny summer days.
- The `fast_charging` feature does not have configurable instantaneous power limit. Consider setting global `max_charge_power` to prevent excessive consumption.
