class Segment:
    def __init__(self, text, start, duration):
        self.text = text
        self.start = start
        self.duration = duration


def make_segment(text, start, duration):
    return Segment(text, start, duration)
