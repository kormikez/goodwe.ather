#!/usr/bin/env python3
import platform
import sys

if platform.system() != "Linux":
    print("Sorry, this script only works on Linux.")
    sys.exit(1)

import asyncio
import subprocess
import ipaddress
import re
import goodwe


def get_local_network():
    route = subprocess.check_output(
        ["ip", "route", "show", "default"], text=True
    )
    iface = re.search(r"dev (\S+)", route).group(1)
    addr = subprocess.check_output(
        ["ip", "-4", "addr", "show", iface], text=True
    )
    cidr = re.search(r"inet (\d+\.\d+\.\d+\.\d+/\d+)", addr).group(1)
    interface = ipaddress.ip_interface(cidr)
    return interface.network


async def check(host):
    try:
        inv = await goodwe.connect(str(host), timeout=1)
        return host
    except Exception:
        return None


async def main():
    network = get_local_network()
    print(f"Scanning network: {network}")
    tasks = [
        asyncio.create_task(check(ip))
        for ip in network.hosts()
    ]
    try:
        for future in asyncio.as_completed(tasks):
            result = await future

            if result:
                print(f"Bingo! Inverter address ---> {result}")

                for t in tasks:
                    t.cancel()
                return

        print("No GoodWe inverter found")
    finally:
        await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
