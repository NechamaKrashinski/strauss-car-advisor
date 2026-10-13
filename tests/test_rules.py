import pytest

from engine.rules import (
    GroupNotAllowed,
    NotEligibleForWaiver,
    UnknownGroup,
    assert_group_allowed,
    budget_for_group,
    eligible_groups,
    electric_vehicle_bonus,
    is_eligible_for_kids_track,
    kids_track_gap_split,
    waiver_allowance,
)


def test_budget_by_group():
    assert budget_for_group("א") == 3500
    assert budget_for_group("ד") == 5200


def test_unknown_group_raises():
    with pytest.raises(UnknownGroup):
        budget_for_group("ה")


def test_eligible_groups_lowest_can_only_choose_itself():
    assert eligible_groups("א") == ["א"]


def test_eligible_groups_highest_can_choose_all():
    assert eligible_groups("ד") == ["א", "ב", "ג", "ד"]


def test_group_allowed_downgrade_ok():
    assert_group_allowed(employee_group="ד", chosen_group="ב")  # לא אמור להעלות חריגה


def test_group_not_allowed_upgrade():
    with pytest.raises(GroupNotAllowed):
        assert_group_allowed(employee_group="ג", chosen_group="ד")


def test_electric_vehicle_bonus_value():
    assert electric_vehicle_bonus() == 250


def test_kids_track_split_with_gap():
    split = kids_track_gap_split(budget=3500, car_cost=6000)
    assert split.gap == 2500
    assert split.employer_share == 1250
    assert split.employee_share == 1250


def test_kids_track_split_no_gap_when_budget_covers_cost():
    split = kids_track_gap_split(budget=5000, car_cost=4500)
    assert split.gap == 0
    assert split.employer_share == 0
    assert split.employee_share == 0


def test_is_eligible_for_kids_track():
    assert is_eligible_for_kids_track(num_children=4, max_child_age_in_household=15) is True
    assert is_eligible_for_kids_track(num_children=3, max_child_age_in_household=15) is False
    assert is_eligible_for_kids_track(num_children=5, max_child_age_in_household=24) is False


def test_waiver_allowance_known_occupation():
    assert waiver_allowance("נהג/ת משנה") == 1200


def test_waiver_allowance_unknown_occupation_raises():
    with pytest.raises(NotEligibleForWaiver):
        waiver_allowance("קוסם/ת")


def test_waiver_allowance_explicitly_not_eligible_raises():
    with pytest.raises(NotEligibleForWaiver):
        waiver_allowance("עובד/ת משרד (לא זכאי לוויתור)")
