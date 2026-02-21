# Test type: API integration
# Validation: Endpoint contracts for parse, returns, and performance APIs
# Command: pytest -q

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_parse_endpoint_success():
    response = client.post(
        "/blackrock/challenge/v1/transactions:parse",
        json={
            "expenses": [
                {"timestamp": "2023-10-12 20:15:00", "amount": 250},
                {"timestamp": "2023-02-28 15:49:00", "amount": 375},
            ]
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert payload == [
        {
            "date": "2023-10-12 20:15:00",
            "amount": 250.0,
            "ceiling": 300.0,
            "remanent": 50.0,
        },
        {
            "date": "2023-02-28 15:49:00",
            "amount": 375.0,
            "ceiling": 400.0,
            "remanent": 25.0,
        },
    ]


def test_parse_endpoint_accepts_challenge_list_date_payload():
    response = client.post(
        "/blackrock/challenge/v1/transactions:parse",
        json=[
            {"date": "2023-10-12 20:15:30", "amount": 250},
            {"date": "2023-02-28 15:49:20", "amount": 375},
            {"date": "2023-07-01 21:59:00", "amount": 620},
            {"date": "2023-12-17 08:09:45", "amount": 480},
        ],
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload == [
        {
            "date": "2023-10-12 20:15:30",
            "amount": 250.0,
            "ceiling": 300.0,
            "remanent": 50.0,
        },
        {
            "date": "2023-02-28 15:49:20",
            "amount": 375.0,
            "ceiling": 400.0,
            "remanent": 25.0,
        },
        {
            "date": "2023-07-01 21:59:00",
            "amount": 620.0,
            "ceiling": 700.0,
            "remanent": 80.0,
        },
        {
            "date": "2023-12-17 08:09:45",
            "amount": 480.0,
            "ceiling": 500.0,
            "remanent": 20.0,
        },
    ]


def test_returns_nps_endpoint_success():
    response = client.post(
        "/blackrock/challenge/v1/returns:nps",
        json={
            "age": 29,
            "wage": 50000,
            "inflation": 0.055,
            "q": [{"fixed": 0, "start": "2023-07-01 00:00", "end": "2023-07-31 23:59"}],
            "p": [
                {
                    "extra": 25,
                    "start": "2023-10-01 08:00",
                    "end": "2023-12-31 19:59",
                }
            ],
            "k": [
                {"start": "2023-03-01 00:00", "end": "2023-11-30 23:59"},
                {"start": "2023-01-01 00:00", "end": "2023-12-31 23:59"},
            ],
            "transactions": [
                {
                    "date": "2023-10-12 20:15:00",
                    "amount": 250,
                    "ceiling": 300,
                    "remanent": 50,
                },
                {
                    "date": "2023-02-28 15:49:00",
                    "amount": 375,
                    "ceiling": 400,
                    "remanent": 25,
                },
                {
                    "date": "2023-07-01 21:59:00",
                    "amount": 620,
                    "ceiling": 700,
                    "remanent": 80,
                },
                {
                    "date": "2023-12-17 08:09:00",
                    "amount": 480,
                    "ceiling": 500,
                    "remanent": 20,
                },
            ],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["savingsByDates"][0]["amount"] == 75.0
    assert payload["savingsByDates"][1]["amount"] == 145.0
    assert payload["savingsByDates"][1]["taxBenefit"] == 0.0


def test_returns_nps_accepts_date_amount_transactions_and_percent_inflation():
    response = client.post(
        "/blackrock/challenge/v1/returns:nps",
        json={
            "age": 29,
            "wage": 50000,
            "inflation": 5.5,
            "q": [
                {
                    "fixed": 0,
                    "start": "2023-07-01 00:00:00",
                    "end": "2023-07-31 23:59:59",
                }
            ],
            "p": [
                {
                    "extra": 25,
                    "start": "2023-10-01 08:00:00",
                    "end": "2023-12-31 19:59:59",
                }
            ],
            "k": [{"start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:59"}],
            "transactions": [
                {"date": "2023-02-28 15:49:20", "amount": 375},
                {"date": "2023-07-01 21:59:00", "amount": 620},
                {"date": "2023-10-12 20:15:30", "amount": 250},
                {"date": "2023-10-12 20:15:30", "amount": 300},
                {"date": "2023-12-17 08:09:45", "amount": -10},
            ],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["transactionsTotalAmount"] == 1245.0
    assert payload["transactionsTotalCeiling"] == 1400.0
    assert payload["savingsByDates"][0]["amount"] == 100.0


def test_returns_endpoint_invalid_k_date_returns_400():
    response = client.post(
        "/blackrock/challenge/v1/returns:nps",
        json={
            "age": 29,
            "wage": 50000,
            "inflation": 5.5,
            "q": [],
            "p": [],
            "k": [{"start": "2023-03-01 00:00:00", "end": "2023-11-31 23:59:59"}],
            "transactions": [{"date": "2023-02-28 15:49:20", "amount": 375}],
        },
    )
    assert response.status_code == 400


def test_returns_endpoint_all_invalid_transactions_returns_400():
    response = client.post(
        "/blackrock/challenge/v1/returns:nps",
        json={
            "age": 29,
            "wage": 50000,
            "inflation": 5.5,
            "q": [],
            "p": [],
            "k": [{"start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:59"}],
            "transactions": [
                {"date": "2023-12-17 08:09:45", "amount": -10},
                {"date": "2023-12-17 08:09:45", "amount": -20},
            ],
        },
    )
    assert response.status_code == 400
    assert "No valid transactions available" in response.json()["detail"]


def test_filter_endpoint_rejects_q_fixed_upper_bound():
    response = client.post(
        "/blackrock/challenge/v1/transactions:filter",
        json={
            "q": [
                {
                    "fixed": 500000,
                    "start": "2023-07-01 00:00:00",
                    "end": "2023-07-31 23:59:59",
                }
            ],
            "p": [],
            "k": [{"start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:59"}],
            "transactions": [{"date": "2023-02-28 15:49:20", "amount": 375}],
        },
    )
    assert response.status_code == 400
    assert "q.fixed must be < 500000" in response.json()["detail"]


def test_filter_endpoint_rejects_p_extra_upper_bound():
    response = client.post(
        "/blackrock/challenge/v1/transactions:filter",
        json={
            "q": [],
            "p": [
                {
                    "extra": 500000,
                    "start": "2023-10-01 00:00:00",
                    "end": "2023-12-31 23:59:59",
                }
            ],
            "k": [{"start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:59"}],
            "transactions": [{"date": "2023-02-28 15:49:20", "amount": 375}],
        },
    )
    assert response.status_code == 400
    assert "p.extra must be < 500000" in response.json()["detail"]


def test_validator_endpoint_excludes_adjusted_remanent():
    response = client.post(
        "/blackrock/challenge/v1/transactions:validator",
        json={
            "wage": 50000,
            "transactions": [
                {
                    "date": "2023-10-12 20:15:30",
                    "amount": 250,
                    "ceiling": 300,
                    "remanent": 50,
                }
            ],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] == [
        {
            "date": "2023-10-12 20:15:30",
            "amount": 250.0,
            "ceiling": 300.0,
            "remanent": 50.0,
        }
    ]
    assert "adjustedRemanent" not in payload["valid"][0]


def test_filter_endpoint_accepts_date_amount_input_and_marks_invalids():
    response = client.post(
        "/blackrock/challenge/v1/transactions:filter",
        json={
            "q": [
                {
                    "fixed": 0,
                    "start": "2023-07-01 00:00:00",
                    "end": "2023-07-31 23:59:59",
                }
            ],
            "p": [
                {
                    "extra": 30,
                    "start": "2023-10-01 00:00:00",
                    "end": "2023-12-31 23:59:59",
                }
            ],
            "k": [{"start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:59"}],
            "wage": 50000,
            "transactions": [
                {"date": "2023-02-28 15:49:20", "amount": 375},
                {"date": "2023-07-15 10:30:00", "amount": 620},
                {"date": "2023-10-12 20:15:30", "amount": 250},
                {"date": "2023-10-12 20:15:30", "amount": 250},
                {"date": "2023-12-17 08:09:45", "amount": -480},
            ],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "valid": [
            {
                "date": "2023-02-28 15:49:20",
                "amount": 375.0,
                "ceiling": 400.0,
                "remanent": 25.0,
                "inKPeriod": True,
            },
            {
                "date": "2023-10-12 20:15:30",
                "amount": 250.0,
                "ceiling": 300.0,
                "remanent": 80.0,
                "inKPeriod": True,
            },
        ],
        "invalid": [
            {
                "date": "2023-10-12 20:15:30",
                "amount": 250.0,
                "message": "Duplicate transaction",
            },
            {
                "date": "2023-12-17 08:09:45",
                "amount": -480.0,
                "message": "Negative amounts are not allowed",
            },
        ],
    }


def test_performance_endpoint_success():
    client.get("/health")
    response = client.get("/blackrock/challenge/v1/performance")
    assert response.status_code == 200
    payload = response.json()
    assert payload["time"].endswith("ms")
    assert payload["memory"].endswith("MB")
    assert isinstance(payload["threads"], int)
