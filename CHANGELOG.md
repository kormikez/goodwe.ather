# goodwe.ather changelog

## v0.2

- Cloud cover forecast replaced with irradiance which is much more relevant for PVE
- The SOC calculation is now affected by sunset proximity as well
- Added 'skip-hours' to ignore forecast for time consumed by charging
- The script will now re-try on failure (up to DEFAULT_MAX_TRIES)

## v0.1

- First published version, based on cloud cover forecast.
