"""
שליפת שווי שימוש ממאגר רשות המסים.

מקור: data/usage_value_2026.csv (הומר מהקובץ הרשמי windows-1255 ל-UTF-8,
ראו docs/spec.md). המפתח הרשמי הייחודי שאומת ללא כפילויות על פני 77,988
השורות הוא (vehicle_type_code, manufacturer_code, model_code, registration_year).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

DEFAULT_CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "usage_value_2026.csv"

KEY_COLUMNS = ["vehicle_type_code", "manufacturer_code", "model_code", "registration_year"]


class UsageValueNotFound(Exception):
    """לא נמצאה אף שורה התואמת את המפתח שסופק."""


class UsageValueAmbiguous(Exception):
    """נמצאו כמה שורות שונות — אסור לנחש, יש לשאול את העובד/הנציג."""

    def __init__(self, matches: list[dict]):
        self.matches = matches
        super().__init__(f"{len(matches)} שורות תואמות, נדרשת הבהרה")


@dataclass(frozen=True)
class UsageValueRecord:
    manufacturer_code: str
    manufacturer_name: str
    model_code: str
    model_description: str
    trade_name: str
    registration_year: int
    vehicle_type_code: str
    fuel_type_code: str
    propulsion_type: str
    is_automatic: str
    usage_value: float
    list_price: float
    adjusted_price: float

    @classmethod
    def from_row(cls, row: pd.Series) -> "UsageValueRecord":
        return cls(
            manufacturer_code=row["manufacturer_code"],
            manufacturer_name=row["manufacturer_name"],
            model_code=row["model_code"],
            model_description=row["model_description"],
            trade_name=row["trade_name"],
            registration_year=int(row["registration_year"]),
            vehicle_type_code=row["vehicle_type_code"],
            fuel_type_code=row["fuel_type_code"],
            propulsion_type=row["propulsion_type"],
            is_automatic=row["is_automatic"],
            usage_value=float(row["usage_value"]),
            list_price=float(row["list_price"]),
            adjusted_price=float(row["adjusted_price"]),
        )


@lru_cache(maxsize=1)
def _load_table(csv_path: str = str(DEFAULT_CSV_PATH)) -> pd.DataFrame:
    df = pd.read_csv(csv_path, dtype=str)
    numeric_cols = ["registration_year", "usage_value", "list_price", "adjusted_price"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def find_usage_value(
    manufacturer_code: str,
    model_code: str,
    registration_year: int,
    vehicle_type_code: str | None = None,
    csv_path: str = str(DEFAULT_CSV_PATH),
) -> UsageValueRecord:
    """
    שליפה לפי המפתח הרשמי. אם vehicle_type_code לא סופק וקיימת יותר משורה
    אחת תואמת (לדוגמה: אותו דגם קיים כפרטי וכמסחרי) — מעלה UsageValueAmbiguous
    במקום לנחש, בהתאם לכלל "אף פעם לא מנחשים ולא ממציאים".
    """
    df = _load_table(csv_path)
    mask = (
        (df["manufacturer_code"] == manufacturer_code)
        & (df["model_code"] == model_code)
        & (df["registration_year"] == registration_year)
    )
    if vehicle_type_code is not None:
        mask &= df["vehicle_type_code"] == vehicle_type_code

    matches = df[mask]
    if len(matches) == 0:
        raise UsageValueNotFound(
            f"לא נמצא רכב תואם: תוצר={manufacturer_code}, דגם={model_code}, "
            f"שנת רישום={registration_year}, קוד סוג רכב={vehicle_type_code}"
        )
    if len(matches) > 1:
        raise UsageValueAmbiguous([row.to_dict() for _, row in matches.iterrows()])

    return UsageValueRecord.from_row(matches.iloc[0])


def search_by_name(
    query: str,
    limit: int = 20,
    csv_path: str = str(DEFAULT_CSV_PATH),
) -> list[UsageValueRecord]:
    """חיפוש חופשי לפי שם יצרן/כינוי מסחרי/תיאור דגם — עזר לבוט/ממשק להציע התאמות."""
    df = _load_table(csv_path)
    q = query.strip()
    if not q:
        return []
    text_mask = (
        df["manufacturer_name"].str.contains(q, case=False, na=False)
        | df["trade_name"].str.contains(q, case=False, na=False)
        | df["model_description"].str.contains(q, case=False, na=False)
    )
    results = df[text_mask].head(limit)
    return [UsageValueRecord.from_row(row) for _, row in results.iterrows()]
