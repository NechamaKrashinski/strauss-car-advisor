"""
טעינת config/rules.yaml ובדיקות זכאות: תקציב לפי קבוצה, מסלול ברוכת ילדים,
רכב חשמלי, ויתור על רכב. ראו docs/spec.md לכללים המקוריים ו-config/rules.yaml
לסימוני "dummy" על נתונים שטרם התקבלו משטראוס.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

DEFAULT_RULES_PATH = Path(__file__).resolve().parent.parent / "config" / "rules.yaml"


class GroupNotAllowed(Exception):
    """העובד ניסה לבחור רכב מקבוצה גבוהה מקבוצת הזכאות שלו."""


class UnknownGroup(Exception):
    pass


class NotEligibleForWaiver(Exception):
    """העיסוק לא מופיע ברשימת העיסוקים הרשאים לוותר על רכב, או שהוא מסומן כלא-זכאי."""


@dataclass(frozen=True)
class KidsTrackSplit:
    car_cost: float
    budget: float
    gap: float
    employer_share: float
    employee_share: float


@lru_cache(maxsize=1)
def load_rules(path: str = str(DEFAULT_RULES_PATH)) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def budget_for_group(group: str, rules: dict | None = None) -> float:
    rules = rules or load_rules()
    budgets = rules["monthly_car_budget_by_group"]
    if group not in budgets:
        raise UnknownGroup(f"קבוצה לא מוכרת: {group}")
    return float(budgets[group])


def eligible_groups(employee_group: str, rules: dict | None = None) -> list[str]:
    """קבוצות שמהן מותר לעובד לבחור רכב: הקבוצה שלו או נמוכה ממנה (תקציב קטן/שווה)."""
    rules = rules or load_rules()
    order = rules["group_order"]
    if employee_group not in order:
        raise UnknownGroup(f"קבוצה לא מוכרת: {employee_group}")
    idx = order.index(employee_group)
    return order[: idx + 1]


def assert_group_allowed(employee_group: str, chosen_group: str, rules: dict | None = None) -> None:
    rules = rules or load_rules()
    allowed = eligible_groups(employee_group, rules)
    if chosen_group not in allowed:
        raise GroupNotAllowed(
            f"עובד/ת בקבוצה {employee_group} לא יכול/ה לבחור רכב מקבוצה {chosen_group} "
            f"(מותר רק: {', '.join(allowed)})"
        )


def electric_vehicle_bonus(rules: dict | None = None) -> float:
    rules = rules or load_rules()
    return float(rules["electric_vehicle"]["monthly_net_bonus"])


def kids_track_gap_split(budget: float, car_cost: float, rules: dict | None = None) -> KidsTrackSplit:
    """
    מחלק את הפער בין התקציב לעלות הרכב במסלול ברוכת ילדים, לפי אחוזי
    employer_share_of_gap / employee_share_of_gap (ברירת מחדל 50/50).
    אם העלות לא עולה על התקציב — אין פער, שני הצדדים משלמים 0.
    """
    rules = rules or load_rules()
    cfg = rules["kids_track"]
    gap = max(0.0, car_cost - budget)
    return KidsTrackSplit(
        car_cost=car_cost,
        budget=budget,
        gap=gap,
        employer_share=gap * cfg["employer_share_of_gap"],
        employee_share=gap * cfg["employee_share_of_gap"],
    )


def is_eligible_for_kids_track(num_children: int, max_child_age_in_household: int | None, rules: dict | None = None) -> bool:
    rules = rules or load_rules()
    cfg = rules["kids_track"]
    if num_children < cfg["min_children"]:
        return False
    if max_child_age_in_household is not None and max_child_age_in_household > cfg["max_child_age"]:
        # כל הילדים מעל הגיל המותר - אין זכאות (יש לבדוק ברמת ילד בודד בהמשך אם צריך דיוק רב יותר)
        return False
    return True


def waiver_allowance(occupation: str, rules: dict | None = None) -> float:
    """
    מחזיר את סכום "אחזקת הרכב" החודשי לעיסוק נתון. מעלה NotEligibleForWaiver
    אם העיסוק לא ברשימה, או שהוא ברשימה עם ערך null (לא רשאי/ת לוותר).
    """
    rules = rules or load_rules()
    table = rules["car_waiver"]["occupation_allowances"]
    if occupation not in table:
        raise NotEligibleForWaiver(
            f"העיסוק '{occupation}' לא מופיע בטבלת העיסוקים הרשאים לוותר על רכב"
        )
    allowance = table[occupation]
    if allowance is None:
        raise NotEligibleForWaiver(f"העיסוק '{occupation}' אינו זכאי לוויתור על רכב")
    return float(allowance)
