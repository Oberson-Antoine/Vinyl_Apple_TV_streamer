from app.audio.ring_buffer import RingBuffer


def test_append_and_snapshot_returns_all_data_under_cap():
    buf = RingBuffer(max_seconds=10, bytes_per_second=4)
    buf.append(b"aaaa")
    buf.append(b"bbbb")
    assert buf.snapshot(seconds=10, bytes_per_second=4) == b"aaaabbbb"


def test_append_trims_oldest_data_over_cap():
    # max 2 "frames" of 4 bytes each = 8 bytes total
    buf = RingBuffer(max_seconds=2, bytes_per_second=4)
    buf.append(b"aaaa")
    buf.append(b"bbbb")
    buf.append(b"cccc")  # should push out the first chunk
    assert buf.snapshot(seconds=2, bytes_per_second=4) == b"bbbbcccc"


def test_snapshot_returns_only_requested_tail():
    buf = RingBuffer(max_seconds=10, bytes_per_second=4)
    buf.append(b"aaaa")
    buf.append(b"bbbb")
    buf.append(b"cccc")
    # want only the last 2 "seconds" worth (8 bytes) out of 12 buffered
    assert buf.snapshot(seconds=2, bytes_per_second=4) == b"bbbbcccc"


def test_snapshot_on_empty_buffer_returns_empty_bytes():
    buf = RingBuffer(max_seconds=10, bytes_per_second=4)
    assert buf.snapshot(seconds=5, bytes_per_second=4) == b""
