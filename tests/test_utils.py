import datetime as dt
import decimal
import uuid

from aws_mcp_server.utils import jsonable


def test_jsonable_converts_common_non_json_values() -> None:
    identifier = uuid.UUID("12345678-1234-5678-1234-567812345678")
    value = {
        "date": dt.date(2026, 11, 9),
        "amount": decimal.Decimal("12.50"),
        "identifier": identifier,
        "items": (b"abc",),
    }

    assert jsonable(value) == {
        "date": "2026-11-09",
        "amount": 12.5,
        "identifier": str(identifier),
        "items": ["<3 bytes>"],
    }