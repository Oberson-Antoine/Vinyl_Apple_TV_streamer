from app.audio.devices import parse_arecord_l

SAMPLE_ARECORD_L = """\
**** List of CAPTURE Hardware Devices ****
card 1: Microphone [Fifine K658  Microphone], device 0: USB Audio [USB Audio]
  Subdevices: 1/1
  Subdevice #0: subdevice #0
card 3: Generic [HD-Audio Generic], device 0: ALC897 Analog [ALC897 Analog]
  Subdevices: 1/1
  Subdevice #0: subdevice #0
card 3: Generic [HD-Audio Generic], device 2: ALC897 Alt Analog [ALC897 Alt Analog]
  Subdevices: 1/1
  Subdevice #0: subdevice #0
card 4: CODEC [USB Audio CODEC], device 0: USB Audio [USB Audio]
  Subdevices: 1/1
  Subdevice #0: subdevice #0
"""


def test_parses_all_capture_devices():
    devices = parse_arecord_l(SAMPLE_ARECORD_L)
    assert [d.device_string for d in devices] == [
        "plughw:CARD=Microphone,DEV=0",
        "plughw:CARD=Generic,DEV=0",
        "plughw:CARD=Generic,DEV=2",
        "plughw:CARD=CODEC,DEV=0",
    ]


def test_description_includes_card_and_device_name():
    devices = parse_arecord_l(SAMPLE_ARECORD_L)
    codec = next(d for d in devices if d.device_string == "plughw:CARD=CODEC,DEV=0")
    assert codec.description == "USB Audio CODEC (USB Audio)"


def test_ignores_non_card_lines():
    devices = parse_arecord_l("**** List of CAPTURE Hardware Devices ****\n")
    assert devices == []


def test_empty_input_returns_empty_list():
    assert parse_arecord_l("") == []
