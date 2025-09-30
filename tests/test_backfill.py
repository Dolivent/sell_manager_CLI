import os
from sellmanagement.download_manager import backfill_halfhours_for_ticker
from sellmanagement.cache import _key_to_path, load_bars


class FakeIB:
    def __init__(self, pages):
        # pages is a list of lists of bars to return sequentially
        self.pages = list(pages)

    def download_halfhours(self, token: str, duration: str = "31 D", max_bars: int | None = 31, endDateTime: str = ""):
        if not self.pages:
            return []
        return self.pages.pop(0)


def test_backfill_halfhours_for_ticker(tmp_path):
    token = "TEST:FOO"
    # ensure cache file removed
    p = _key_to_path(f"{token}:30m")
    try:
        if p.exists():
            p.unlink()
    except Exception:
        pass

    # pages: two pages of 2 bars each then one page of 2 bars -> total 6
    pages = [
        [{"Date": "2025-01-01T10:00:00", "Close": 1}, {"Date": "2025-01-01T09:30:00", "Close": 2}],
        [{"Date": "2024-12-31T16:00:00", "Close": 3}, {"Date": "2024-12-31T15:30:00", "Close": 4}],
        [{"Date": "2024-12-30T16:00:00", "Close": 5}, {"Date": "2024-12-30T15:30:00", "Close": 6}],
    ]
    fake = FakeIB(pages)

    # run backfill with small target
    backfill_halfhours_for_ticker(fake, token, bars_per_call=2, target_bars=5)

    bars = load_bars(f"{token}:30m")
    assert len(bars) >= 5


