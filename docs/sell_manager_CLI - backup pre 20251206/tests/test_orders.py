from sellmanagement.orders import prepare_close_order, execute_order


def test_prepare_and_simulate():
    p = prepare_close_order('NASDAQ:TEST', 10)
    assert p.symbol == 'NASDAQ:TEST'
    res = execute_order(None, p, dry_run=True)
    assert res['status'] == 'simulated'


