"""
בדיקות למנוע ההשוואה. שימו לב: דוגמת התסריט המקורית מה-PDF (נטו 11,480 ->
11,690, הפרש 210+) אינה ניתנת לשחזור מדויק כבדיקת-רגרסיה, כי ה-PDF עצמו
מציין את הפרש שווי השימוש (310 ₪) כ"לדוגמה" ולא נותן את פרטי הרכב הנוכחי
של העובד. לכן הבדיקות כאן משתמשות ברכבים אמיתיים מה-CSV ובודקות נכונות
מבנית וכיוון ההפרש, לא התאמה למספר "קסום" מהתסריט. ראו docs/spec.md.
"""

from engine.comparison import compare, scenario_from_vehicle, scenario_from_waiver
from engine.net_calculator import SalaryInputs


def test_compare_gas_car_vs_electric_upgrade_improves_net():
    salary = SalaryInputs(
        base_salary=14200,
        variable_components=1000,
        pension_employee_rate=0.06,
        keren_hishtalmut_employee_rate=0.025,
        credit_points=2.25,
    )

    current, current_record = scenario_from_vehicle(
        label="הרכב הנוכחי (BMW M440i xDrive)",
        manufacturer_code="00143",
        model_code="02339",
        registration_year=2024,
        vehicle_type_code="1",
        employee_participation=0,
    )
    alternative, alt_record = scenario_from_vehicle(
        label="רכב חשמלי (Audi Q4 e-tron)",
        manufacturer_code="00019",
        model_code="01126",
        registration_year=2024,
        vehicle_type_code="1",
        employee_participation=300,
        is_electric=True,
    )

    assert current_record.usage_value == 12020
    assert alt_record.usage_value == 7680
    assert alternative.electric_vehicle_bonus == 250

    result = compare(salary, current, alternative)

    # שווי שימוש נמוך משמעותית (12,020 -> 7,680) + בונוס 250, מול השתתפות
    # חדשה של 300 - הירידה בבסיס המס גוברת על ההשתתפות, אז הנטו אמור לעלות.
    assert result.net_diff > 0
    assert result.net_diff == round(result.alternative.net_pay - result.current.net_pay, 2)
    assert "הרכב הנוכחי" in result.explanation_lines[0]
    assert any("250" in line for line in result.explanation_lines)


def test_compare_car_vs_waiver_for_eligible_occupation():
    salary = SalaryInputs(base_salary=10000, credit_points=2.25)

    current, _ = scenario_from_vehicle(
        label="הרכב הנוכחי",
        manufacturer_code="00019",
        model_code="01126",
        registration_year=2024,
        vehicle_type_code="1",
    )
    alternative = scenario_from_waiver(
        label="ויתור על רכב",
        occupation="איש/אשת מכירות שטח",
    )

    result = compare(salary, current, alternative)

    assert alternative.car_waiver_allowance == 1500
    assert result.alternative.cash_components == 10000 + 1500
    assert result.net_diff == round(result.alternative.net_pay - result.current.net_pay, 2)
    assert any("אחזקת רכב" in line for line in result.explanation_lines)
