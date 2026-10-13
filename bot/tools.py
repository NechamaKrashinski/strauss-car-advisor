"""
כלים שה-LLM יכול לקרוא (tool calling). כל כלי עוטף פונקציה טהורה מתוך
engine/ ומחזיר dict מובנה - גם במקרה שגיאה (לא מעלה חריגה ל-LLM, כדי שהמודל
יוכל להגיב בצורה הגיונית, למשל לשאול שאלת הבהרה). חוק הברזל: הכלים
האלה הם המקום היחיד שבו נגזרים מספרים - ה-LLM אף פעם לא מחשב נטו בעצמו.
"""

from __future__ import annotations

from langchain_core.tools import tool
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from engine import rules as rules_engine
from engine.comparison import compare, scenario_from_kids_track, scenario_from_vehicle, scenario_from_waiver
from engine.net_calculator import SalaryInputs
from engine.rules import GroupNotAllowed, NotEligibleForWaiver, UnknownGroup
from engine.usage_value import UsageValueAmbiguous, UsageValueNotFound, search_by_name


class SalarySchema(BaseModel):
    base_salary: float = Field(description="שכר בסיס חודשי, ברוטו, לפני כל תוספת/ניכוי")
    variable_components: float = Field(default=0.0, description="עמלות/בונוסים משתנים לחודש")
    pension_employee_rate: float = Field(default=0.0, description="אחוז הפרשת העובד/ת לפנסיה, כמספר עשרוני (6% = 0.06)")
    keren_hishtalmut_employee_rate: float = Field(default=0.0, description="אחוז הפרשת העובד/ת לקרן השתלמות, כמספר עשרוני")
    credit_points: float = Field(default=2.25, description="מספר נקודות זיכוי של העובד/ת")


class VehicleScenarioSchema(BaseModel):
    label: str = Field(description="תיאור קצר של החלופה, לדוגמה 'הרכב הנוכחי' או 'רכב חשמלי חדש'")
    manufacturer_code: str | None = Field(default=None, description="קוד תוצר מהמאגר הרשמי")
    model_code: str | None = Field(default=None, description="קוד דגם מהמאגר הרשמי")
    registration_year: int | None = Field(default=None, description="שנת רישום הרכב")
    vehicle_type_code: str | None = Field(default=None, description="קוד סוג רכב, רק אם נדרש לפירוק דו-משמעות")
    employee_participation: float = Field(default=0.0, description="השתתפות העובד/ת בעלות הרכב, בש\"ח לחודש")
    is_electric: bool = Field(default=False, description="האם מדובר ברכב חשמלי (מקבל תוספת 250 ₪ נטו)")
    is_waiver: bool = Field(default=False, description="האם זו חלופת ויתור על רכב (תחת זה לא ממלאים פרטי רכב)")
    occupation: str | None = Field(default=None, description="העיסוק של העובד/ת - נדרש כש-is_waiver=True")
    kids_track: bool = Field(default=False, description="האם זו חלופת מסלול ברוכת ילדים")
    employee_group: str | None = Field(default=None, description="קבוצת הזכאות של העובד/ת (א-ד) - נדרש כש-kids_track=True")
    car_cost: float | None = Field(default=None, description="עלות הרכב במסלול ברוכת ילדים - נדרש כש-kids_track=True")


def _error(message: str) -> dict:
    return {"status": "error", "message": message}


def _build_scenario(v: VehicleScenarioSchema):
    if v.is_waiver:
        if not v.occupation:
            return None, _error("is_waiver=True אבל לא סופק occupation")
        scenario = scenario_from_waiver(label=v.label, occupation=v.occupation)
        return scenario, None

    if not (v.manufacturer_code and v.model_code and v.registration_year):
        return None, _error(
            "חסרים פרטי רכב (manufacturer_code/model_code/registration_year) ולא סומן is_waiver"
        )

    if v.kids_track:
        if not (v.employee_group and v.car_cost):
            return None, _error("kids_track=True אבל חסר employee_group או car_cost")
        scenario, record = scenario_from_kids_track(
            label=v.label,
            manufacturer_code=v.manufacturer_code,
            model_code=v.model_code,
            registration_year=v.registration_year,
            vehicle_type_code=v.vehicle_type_code,
            employee_group=v.employee_group,
            car_cost=v.car_cost,
            base_employee_participation=v.employee_participation,
            is_electric=v.is_electric,
        )
        return scenario, None

    scenario, record = scenario_from_vehicle(
        label=v.label,
        manufacturer_code=v.manufacturer_code,
        model_code=v.model_code,
        registration_year=v.registration_year,
        vehicle_type_code=v.vehicle_type_code,
        employee_participation=v.employee_participation,
        is_electric=v.is_electric,
    )
    return scenario, None


@tool
def search_vehicle(query: str) -> dict:
    """
    חיפוש חופשי של רכב לפי שם יצרן/כינוי מסחרי/תיאור דגם במאגר הרשמי, כדי
    למצוא את קוד תוצר/קוד דגם המדויקים מתוך מה שהעובד/ת אומר/ת בשפה חופשית
    (למשל "טויוטה קורולה 2022"). משתמשים בזה *לפני* get_usage_value אם אין
    קודים מדויקים ביד. אף פעם לא מנחשים קוד - משתמשים רק בתוצאה שחוזרת כאן.
    """
    try:
        results = search_by_name(query, limit=15)
    except Exception as exc:  # noqa: BLE001 - גבול כלי: שגיאה חוזרת כמידע למודל, לא קורסת
        return _error(str(exc))
    if not results:
        return {"status": "not_found", "matches": []}
    return {
        "status": "ok",
        "matches": [
            {
                "manufacturer_code": r.manufacturer_code,
                "manufacturer_name": r.manufacturer_name,
                "model_code": r.model_code,
                "trade_name": r.trade_name,
                "model_description": r.model_description,
                "registration_year": r.registration_year,
                "vehicle_type_code": r.vehicle_type_code,
                "usage_value": r.usage_value,
            }
            for r in results
        ],
    }


@tool
def get_usage_value(
    manufacturer_code: str,
    model_code: str,
    registration_year: int,
    vehicle_type_code: str | None = None,
) -> dict:
    """
    שליפת שווי שימוש רשמי לרכב ספציפי מהמאגר, לפי קוד תוצר + קוד דגם + שנת
    רישום (ואם צריך גם קוד סוג רכב). אם status='ambiguous' - יש כמה רכבים
    תואמים, צריך לבקש מהעובד/ת פרט מבחין נוסף (כמו קוד סוג רכב) ולא לנחש.
    """
    try:
        record = rules_engine  # placeholder to keep import used; real call below
        from engine.usage_value import find_usage_value

        rec = find_usage_value(manufacturer_code, model_code, registration_year, vehicle_type_code)
    except UsageValueNotFound as exc:
        return {"status": "not_found", "message": str(exc)}
    except UsageValueAmbiguous as exc:
        return {"status": "ambiguous", "matches": exc.matches}
    return {
        "status": "ok",
        "usage_value": rec.usage_value,
        "manufacturer_name": rec.manufacturer_name,
        "trade_name": rec.trade_name,
    }


@tool
def check_group_eligibility(employee_group: str, chosen_group: str) -> dict:
    """
    בודק האם מותר לעובד/ת מקבוצת זכאות מסוימת לבחור רכב מקבוצה אחרת (מותר
    רק מהקבוצה שלו/ה או נמוכה ממנה, לא גבוהה יותר).
    """
    try:
        rules_engine.assert_group_allowed(employee_group, chosen_group)
    except (UnknownGroup, GroupNotAllowed) as exc:
        return {"status": "not_allowed", "message": str(exc)}
    return {"status": "ok"}


@tool
def check_waiver_eligibility(occupation: str) -> dict:
    """
    בודק האם עיסוק נתון זכאי לוותר על רכב, ואם כן - מה סכום "אחזקת הרכב"
    החודשי החלופי. ⚠️ טבלת העיסוקים כרגע היא נתוני דמה (DUMMY) עד שיגיעו
    הנתונים האמיתיים משטראוס - יש לציין זאת לעובד/ת אם רלוונטי.
    """
    try:
        allowance = rules_engine.waiver_allowance(occupation)
    except NotEligibleForWaiver as exc:
        return {"status": "not_eligible", "message": str(exc)}
    return {"status": "ok", "monthly_allowance": allowance, "dummy_data": True}


@tool
def calculate_net_comparison(salary: SalarySchema, current: VehicleScenarioSchema, alternative: VehicleScenarioSchema) -> dict:
    """
    מריץ את מנוע ההשוואה המלא: בונה את שני התרחישים (היום מול חלופה), שולף
    שווי שימוש אמיתי לכל רכב, מחשב נטו לשניהם, ומחזיר את ההפרש + פירוט
    הסבר. זהו הכלי היחיד שמחזיר "נטו" סופי - אסור לחשב נטו בשום דרך אחרת.
    אם status='error' בתוצאה של current/alternative - חסר מידע, יש לשאול
    את העובד/ת (או את הנציג/ה דרך ask_representative) ולא להמשיך בניחוש.
    """
    salary_inputs = SalaryInputs(
        base_salary=salary.base_salary,
        variable_components=salary.variable_components,
        pension_employee_rate=salary.pension_employee_rate,
        keren_hishtalmut_employee_rate=salary.keren_hishtalmut_employee_rate,
        credit_points=salary.credit_points,
    )

    current_scenario, current_error = _build_scenario(current)
    if current_error:
        return {"status": "error", "which": "current", **current_error}
    alternative_scenario, alt_error = _build_scenario(alternative)
    if alt_error:
        return {"status": "error", "which": "alternative", **alt_error}

    try:
        result = compare(salary_inputs, current_scenario, alternative_scenario)
    except (UsageValueNotFound, UsageValueAmbiguous, GroupNotAllowed, UnknownGroup, NotEligibleForWaiver) as exc:
        return {"status": "error", "message": str(exc)}

    return {
        "status": "ok",
        "current_label": result.current_label,
        "alternative_label": result.alternative_label,
        "current_net_pay": result.current.net_pay,
        "alternative_net_pay": result.alternative.net_pay,
        "net_diff": result.net_diff,
        "explanation_lines": result.explanation_lines,
    }


@tool
def ask_representative(question: str) -> str:
    """
    שולח שאלה לנציג/ת תחבורה כשחסר מידע שרק הם יכולים לספק (למשל השתתפות
    מדויקת ברכב חדש שעוד לא נקבעה). עוצר את השיחה עד שמתקבלת תשובה - לא
    ממציאים תשובה במקום זה. אחרי קריאה לכלי הזה, המשך השיחה יתקבל כטקסט
    התשובה של הנציג/ה.
    """
    answer = interrupt({"question": question})
    return answer


ALL_TOOLS = [
    search_vehicle,
    get_usage_value,
    check_group_eligibility,
    check_waiver_eligibility,
    calculate_net_comparison,
    ask_representative,
]
