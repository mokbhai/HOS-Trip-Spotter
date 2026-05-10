import pytest

from trips.api.serializers import TripRequestSerializer


VALID_QUICK_DATA = {
    "current_location": "Dallas, TX",
    "pickup_location": "Austin, TX",
    "dropoff_location": "Phoenix, AZ",
    "start_datetime": "2026-05-09T08:00:00+05:30",
    "hos_mode": "quick",
    "current_cycle_used_hours": "12.5",
}


VALID_COMPLIANCE_DATA = {
    "current_location": "Dallas, TX",
    "pickup_location": "Austin, TX",
    "dropoff_location": "Phoenix, AZ",
    "start_datetime": "2026-05-09T08:00:00+05:30",
    "hos_mode": "compliance",
    "prior_8_days": ["8", "9.5", "7", "0", "10", "11", "6.25", "8"],
    "current_duty_status": "off_duty",
    "current_day_driving_used_hours": "4",
    "current_day_on_duty_used_hours": "6.5",
}


def assert_valid(data):
    serializer = TripRequestSerializer(data=data)
    assert serializer.is_valid(), serializer.errors
    return serializer


def assert_invalid(data, field):
    serializer = TripRequestSerializer(data=data)
    assert not serializer.is_valid()
    assert field in serializer.errors
    return serializer


@pytest.mark.django_db
def test_quick_mode_accepts_assignment_required_fields():
    serializer = assert_valid(VALID_QUICK_DATA)

    assert serializer.validated_data["hos_mode"] == "quick"
    assert serializer.validated_data["current_location"] == "Dallas, TX"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "prior_8_days",
    [
        ["8", "9", "7", "0", "10", "11", "6"],
        ["8", "9", "7", "0", "10", "11", "6", "8", "4"],
    ],
)
def test_compliance_mode_requires_exactly_8_prior_day_values(prior_8_days):
    data = {**VALID_COMPLIANCE_DATA, "prior_8_days": prior_8_days}

    assert_invalid(data, "prior_8_days")


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("base_data", "field", "value"),
    [
        (VALID_QUICK_DATA, "current_cycle_used_hours", "-0.1"),
        (VALID_COMPLIANCE_DATA, "prior_8_days", ["8", "9", "7", "0", "-0.1", "11", "6", "8"]),
        (VALID_COMPLIANCE_DATA, "current_day_driving_used_hours", "-0.1"),
        (VALID_COMPLIANCE_DATA, "current_day_on_duty_used_hours", "-0.1"),
    ],
)
def test_hours_cannot_be_negative(base_data, field, value):
    data = {**base_data, field: value}

    assert_invalid(data, field)


@pytest.mark.django_db
def test_current_cycle_used_cannot_exceed_70():
    data = {**VALID_QUICK_DATA, "current_cycle_used_hours": "70.1"}

    assert_invalid(data, "current_cycle_used_hours")


@pytest.mark.django_db
def test_current_day_driving_used_cannot_exceed_11():
    data = {**VALID_COMPLIANCE_DATA, "current_day_driving_used_hours": "11.1"}

    assert_invalid(data, "current_day_driving_used_hours")


@pytest.mark.django_db
def test_current_day_on_duty_used_cannot_exceed_14():
    data = {**VALID_COMPLIANCE_DATA, "current_day_on_duty_used_hours": "14.1"}

    assert_invalid(data, "current_day_on_duty_used_hours")


@pytest.mark.django_db
def test_compliance_mode_rejects_driving_hours_greater_than_on_duty_hours():
    data = {
        **VALID_COMPLIANCE_DATA,
        "current_day_driving_used_hours": "8",
        "current_day_on_duty_used_hours": "7",
    }

    serializer = assert_invalid(data, "current_day_driving_used_hours")
    assert (
        "cannot exceed current_day_on_duty_used_hours"
        in str(serializer.errors["current_day_driving_used_hours"][0])
    )


@pytest.mark.django_db
def test_quick_mode_does_not_require_compliance_only_fields():
    data = {
        "current_location": "Dallas, TX",
        "pickup_location": "Austin, TX",
        "dropoff_location": "Phoenix, AZ",
        "start_datetime": "2026-05-09T08:00:00+05:30",
        "hos_mode": "quick",
        "current_cycle_used_hours": "12.5",
    }

    assert_valid(data)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("prior_8_days", ["8", "9", "7", "0", "10", "11", "6.25", "8"]),
        ("current_duty_status", "off_duty"),
        ("current_day_driving_used_hours", "4"),
        ("current_day_on_duty_used_hours", "6.5"),
    ],
)
def test_quick_mode_rejects_compliance_only_fields_when_present(field, value):
    data = {**VALID_QUICK_DATA, field: value}

    assert_invalid(data, field)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "missing_field",
    [
        "prior_8_days",
        "current_duty_status",
        "current_day_driving_used_hours",
        "current_day_on_duty_used_hours",
    ],
)
def test_compliance_mode_requires_compliance_only_fields(missing_field):
    data = {**VALID_COMPLIANCE_DATA}
    data.pop(missing_field)

    assert_invalid(data, missing_field)


@pytest.mark.django_db
def test_compliance_mode_does_not_require_quick_only_fields():
    assert_valid(VALID_COMPLIANCE_DATA)


@pytest.mark.django_db
def test_compliance_mode_rejects_current_cycle_used_hours_when_present():
    data = {**VALID_COMPLIANCE_DATA, "current_cycle_used_hours": "12.5"}

    assert_invalid(data, "current_cycle_used_hours")


@pytest.mark.django_db
def test_quick_mode_requires_current_cycle_used_hours():
    data = {**VALID_QUICK_DATA}
    data.pop("current_cycle_used_hours")

    assert_invalid(data, "current_cycle_used_hours")
