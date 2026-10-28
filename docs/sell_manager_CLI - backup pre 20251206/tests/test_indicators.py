from sellmanagement.indicators import simple_moving_average, exponential_moving_average


def test_sma_basic():
    vals = [1, 2, 3, 4, 5]
    assert simple_moving_average(vals, 3) == (3 + 4 + 5) / 3.0
    assert simple_moving_average(vals, 5) == sum(vals) / 5.0
    assert simple_moving_average(vals, 6) is None


def test_ema_basic():
    vals = [1.0, 2.0, 3.0, 4.0, 5.0]
    ema3 = exponential_moving_average(vals, 3)
    assert ema3 is not None
    # rough check: ema should be between last price and sma
    sma3 = (3.0 + 4.0 + 5.0) / 3.0
    assert 3.0 <= ema3 <= 5.0


