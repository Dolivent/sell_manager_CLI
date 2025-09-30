from sellmanagement.signals import decide, append_signal


def test_decide_no_data():
    res = decide(100.0, 'SMA', 10, [1,2,3])
    assert res['decision'] == 'Skip'


def test_decide_sell():
    vals = [100.0, 101.0, 102.0, 103.0, 104.0]
    # SMA(3) = (102+103+104)/3 = 103
    res = decide(102.0, 'SMA', 3, vals)
    assert res['decision'] == 'SellSignal'


