from decimal import Decimal

from rest_framework import serializers


class TripRequestSerializer(serializers.Serializer):
    HOS_MODE_CHOICES = ("quick", "compliance")
    DUTY_STATUS_CHOICES = ("off_duty", "sleeper_berth", "driving", "on_duty")

    current_location = serializers.CharField(allow_blank=False, trim_whitespace=True)
    pickup_location = serializers.CharField(allow_blank=False, trim_whitespace=True)
    dropoff_location = serializers.CharField(allow_blank=False, trim_whitespace=True)
    start_datetime = serializers.DateTimeField()
    hos_mode = serializers.ChoiceField(choices=HOS_MODE_CHOICES)

    current_cycle_used_hours = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0"),
        max_value=Decimal("70"),
        required=False,
    )
    prior_8_days = serializers.ListField(
        child=serializers.DecimalField(
            max_digits=5,
            decimal_places=2,
            min_value=Decimal("0"),
            max_value=Decimal("24"),
        ),
        min_length=8,
        max_length=8,
        required=False,
    )
    current_duty_status = serializers.ChoiceField(
        choices=DUTY_STATUS_CHOICES,
        required=False,
    )
    current_day_driving_used_hours = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0"),
        max_value=Decimal("11"),
        required=False,
    )
    current_day_on_duty_used_hours = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0"),
        max_value=Decimal("14"),
        required=False,
    )

    carrier_name = serializers.CharField(
        allow_blank=True,
        required=False,
        trim_whitespace=True,
    )
    main_office_address = serializers.CharField(
        allow_blank=True,
        required=False,
        trim_whitespace=True,
    )
    truck_number = serializers.CharField(
        allow_blank=True,
        required=False,
        trim_whitespace=True,
    )
    trailer_number = serializers.CharField(
        allow_blank=True,
        required=False,
        trim_whitespace=True,
    )
    shipping_document = serializers.CharField(
        allow_blank=True,
        required=False,
        trim_whitespace=True,
    )

    def validate(self, attrs):
        errors = {}

        if attrs.get("hos_mode") == "quick":
            self._require_fields(attrs, errors, ["current_cycle_used_hours"])
            self._reject_fields(
                attrs,
                errors,
                [
                    "prior_8_days",
                    "current_duty_status",
                    "current_day_driving_used_hours",
                    "current_day_on_duty_used_hours",
                ],
            )
        elif attrs.get("hos_mode") == "compliance":
            self._require_fields(
                attrs,
                errors,
                [
                    "prior_8_days",
                    "current_duty_status",
                    "current_day_driving_used_hours",
                    "current_day_on_duty_used_hours",
                ],
            )
            self._reject_fields(attrs, errors, ["current_cycle_used_hours"])
            self._validate_compliance_hour_totals(attrs, errors)

        if errors:
            raise serializers.ValidationError(errors)

        return attrs

    def _require_fields(self, attrs, errors, field_names):
        for field_name in field_names:
            if field_name not in attrs:
                errors[field_name] = ["This field is required."]

    def _reject_fields(self, attrs, errors, field_names):
        for field_name in field_names:
            if field_name in attrs:
                errors[field_name] = ["This field is not valid for the selected HOS mode."]

    def _validate_compliance_hour_totals(self, attrs, errors):
        driving_hours = attrs.get("current_day_driving_used_hours")
        on_duty_hours = attrs.get("current_day_on_duty_used_hours")

        if driving_hours is None or on_duty_hours is None:
            return

        if driving_hours > on_duty_hours:
            errors["current_day_driving_used_hours"] = [
                "current_day_driving_used_hours cannot exceed current_day_on_duty_used_hours."
            ]


class TripPlanRequestSerializer(TripRequestSerializer):
    route_distance_miles = serializers.DecimalField(
        max_digits=8,
        decimal_places=2,
        min_value=Decimal("1"),
        required=False,
    )
    average_speed_mph = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("1"),
        max_value=Decimal("100"),
        required=False,
    )
