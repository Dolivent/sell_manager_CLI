from sellmanagement import aggregator


def test_halfhours_to_hours():
    halfhours = [
        {"Date": "2025-01-01T09:00:00", "Open": 1, "High": 2, "Low": 1, "Close": 2, "Volume": 10},
        {"Date": "2025-01-01T09:30:00", "Open": 2, "High": 3, "Low": 2, "Close": 3, "Volume": 5},
        {"Date": "2025-01-01T10:00:00", "Open": 3, "High": 4, "Low": 3, "Close": 4, "Volume": 7},
        {"Date": "2025-01-01T10:30:00", "Open": 4, "High": 5, "Low": 4, "Close": 5, "Volume": 2},
    ]
    hours = aggregator.halfhours_to_hours(halfhours)
    assert len(hours) == 2
    h0 = hours[0]
    assert h0["Open"] == 1
    assert h0["High"] == 3
    assert h0["Low"] == 1
    assert h0["Close"] == 3
    assert h0["Volume"] == 15


