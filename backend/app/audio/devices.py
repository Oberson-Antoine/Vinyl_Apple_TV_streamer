import asyncio
import re
from dataclasses import dataclass

_CARD_LINE = re.compile(
    r"^card (\d+): (\S+) \[(?P<card_desc>.*?)\], device (?P<dev_num>\d+): .*\[(?P<dev_desc>.*?)\]$"
)


@dataclass
class DeviceInfo:
    device_string: str
    description: str


def parse_arecord_l(text: str) -> list[DeviceInfo]:
    """Parses `arecord -l` output into ALSA device strings usable with `-D`. Uses
    `plughw:CARD=<name>,DEV=<n>` (not bare `hw:`) so ALSA's plug layer handles any
    rate/format conversion the hardware needs."""
    devices = []
    for line in text.splitlines():
        match = _CARD_LINE.match(line.strip())
        if not match:
            continue
        card_name = match.group(2)
        dev_num = match.group("dev_num")
        devices.append(
            DeviceInfo(
                device_string=f"plughw:CARD={card_name},DEV={dev_num}",
                description=f"{match.group('card_desc')} ({match.group('dev_desc')})",
            )
        )
    return devices


async def list_capture_devices() -> list[DeviceInfo]:
    proc = await asyncio.create_subprocess_exec(
        "arecord", "-l", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await proc.communicate()
    return parse_arecord_l(stdout.decode(errors="replace"))
