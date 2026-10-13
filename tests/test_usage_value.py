import pytest

from engine.usage_value import (
    UsageValueAmbiguous,
    UsageValueNotFound,
    find_usage_value,
    search_by_name,
)


def test_find_usage_value_exact_match():
    record = find_usage_value(
        manufacturer_code="00019",
        model_code="00290",
        registration_year=2010,
        vehicle_type_code="1",
    )
    assert record.manufacturer_name == "אאודי"
    assert record.usage_value == 14800


def test_find_usage_value_without_vehicle_type_when_unique():
    # לדגם הזה יש שורה יחידה לשנת 2010 (vehicle_type_code לא נדרש להבחנה)
    record = find_usage_value(
        manufacturer_code="00019",
        model_code="00290",
        registration_year=2010,
    )
    assert record.usage_value == 14800


def test_find_usage_value_ambiguous_without_vehicle_type():
    # ל-00019/01383/2024 יש שתי שורות (vehicle_type_code 1 ו-2) בערכים שונים —
    # אסור לנחש, חייב לעלות שגיאת אי-ודאות.
    with pytest.raises(UsageValueAmbiguous) as exc_info:
        find_usage_value(
            manufacturer_code="00019",
            model_code="01383",
            registration_year=2024,
        )
    assert len(exc_info.value.matches) == 2


def test_find_usage_value_ambiguous_resolved_by_vehicle_type():
    record = find_usage_value(
        manufacturer_code="00019",
        model_code="01383",
        registration_year=2024,
        vehicle_type_code="2",
    )
    assert record.usage_value == 13140


def test_find_usage_value_not_found():
    with pytest.raises(UsageValueNotFound):
        find_usage_value(
            manufacturer_code="99999",
            model_code="99999",
            registration_year=1999,
        )


def test_search_by_name_finds_audi():
    results = search_by_name("אאודי", limit=5)
    assert len(results) > 0
    assert all(r.manufacturer_name == "אאודי" for r in results)


def test_search_by_name_empty_query_returns_nothing():
    assert search_by_name("") == []
