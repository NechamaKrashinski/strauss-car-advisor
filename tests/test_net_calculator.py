from engine.net_calculator import SalaryInputs, VehicleBenefitInputs, calculate_net


def test_simple_salary_no_vehicle():
    """תרחיש פשוט בלי רכב - בודק רק מדרגות מס + נקודות זיכוי + ביטוח לאומי.
    מחושב ידנית: מס גולמי 1,119.6 (10% על 7,010 + 14% על 2,990), פחות זיכוי
    2.25*242=544.5 => מס 575.1. ביטוח לאומי: 7,703*4.27% + 2,297*12.17% = 608.463.
    נטו = 10,000 - 575.1 - 608.463 = 8,816.437 -> 8,816.44."""
    result = calculate_net(SalaryInputs(base_salary=10000, credit_points=2.25))
    assert result.net_pay == 8816.44


def test_salary_with_vehicle_electric_upgrade_scenario():
    """תרחיש מלא עם רכב: בסיס 14,200 + עמלות 1,000, פנסיה 6%, קרן השתלמות 2.5%,
    2.25 נקודות זיכוי, שווי שימוש 2,000, השתתפות 350, תוספת חשמלי 250 נטו.
    מחושב ידנית (ראו תיעוד בקוד הבדיקה שהורץ) -> נטו 10,682.79."""
    result = calculate_net(
        SalaryInputs(
            base_salary=14200,
            variable_components=1000,
            pension_employee_rate=0.06,
            keren_hishtalmut_employee_rate=0.025,
            credit_points=2.25,
        ),
        VehicleBenefitInputs(
            usage_value=2000,
            employee_participation=350,
            electric_vehicle_net_bonus=250,
        ),
    )
    assert result.net_pay == 10682.79
    assert result.gross_taxable_income == 16850.0
    assert result.taxable_income_for_tax == 15558.0


def test_employee_participation_reduces_taxable_addition_and_cash():
    """השתתפות העובד צריכה להפחית גם את שווי השימוש החייב במס וגם את המזומן
    בפועל - לא פעמיים על אותו דבר, אלא פעם אחת בכל ערוץ."""
    without_participation = calculate_net(
        SalaryInputs(base_salary=10000),
        VehicleBenefitInputs(usage_value=1000, employee_participation=0),
    )
    with_participation = calculate_net(
        SalaryInputs(base_salary=10000),
        VehicleBenefitInputs(usage_value=1000, employee_participation=1000),
    )
    # השתתפות מלאה = שווי שימוש חייב במס מתאפס, ומשם הנטו עולה לעומת תשלום
    # השתתפות + מס על שווי מלא
    assert with_participation.non_cash_taxable_addition == 0
    assert with_participation.net_pay != without_participation.net_pay


def test_electric_vehicle_bonus_is_pure_net_addition():
    """תוספת הרכב החשמלי (250 נטו) לא עוברת דרך מנוע המס - משפיעה ישירות על
    הנטו הסופי ולא על ההכנסה החייבת במס."""
    base = calculate_net(SalaryInputs(base_salary=10000))
    with_bonus = calculate_net(
        SalaryInputs(base_salary=10000),
        VehicleBenefitInputs(electric_vehicle_net_bonus=250),
    )
    assert with_bonus.gross_taxable_income == base.gross_taxable_income
    assert round(with_bonus.net_pay - base.net_pay, 2) == 250.0


def test_car_waiver_allowance_excluded_from_pension_base():
    """אחזקת רכב (ויתור) לא כלולה בבסיס הפנסיה/קרן השתלמות (רכיב לא-סוציאלי)."""
    result = calculate_net(
        SalaryInputs(base_salary=10000, pension_employee_rate=0.06),
        VehicleBenefitInputs(car_waiver_allowance=1000),
    )
    assert result.pension_deduction == 600  # 6% מ-10,000 בלבד, לא מ-11,000
    assert result.cash_components == 11000
