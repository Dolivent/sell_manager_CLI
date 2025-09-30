from sellmanagement.indicators import simple_moving_average, exponential_moving_average, series_sma, series_ema


def test_sma_ema_basic():
    vals = [1, 2, 3, 4, 5, 6]
    sm = simple_moving_average(vals, 3)
    assert sm == 5.0
    em = exponential_moving_average(vals, 3)
    assert em is not None

    ss = series_sma(vals, 3)
    assert ss[-1] == 5.0
    se = series_ema(vals, 3)
    assert se[-1] is not None


