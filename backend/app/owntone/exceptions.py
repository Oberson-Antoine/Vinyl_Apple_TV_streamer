class OwnToneUnavailable(Exception):
    """Raised when OwnTone can't be reached or returns an error — lets callers
    distinguish "OwnTone is down" from a genuine bug in our request."""
