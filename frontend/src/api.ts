import type { LocationSuggestion, TripFormState, TripPlan } from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly details?: unknown,
  ) {
    super(message);
  }
}

export async function planTrip(form: TripFormState): Promise<TripPlan> {
  const response = await fetch("/api/trips/plan/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(toPayload(form)),
  });

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(readableError(data), data);
  }

  return data as TripPlan;
}

export async function searchLocations(query: string, signal?: AbortSignal): Promise<LocationSuggestion[]> {
  const response = await fetch(`/api/locations/search/?q=${encodeURIComponent(query)}`, { signal });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(readableError(data), data);
  }

  if (!data || typeof data !== "object" || !Array.isArray((data as { results?: unknown }).results)) {
    return [];
  }

  return (data as { results: LocationSuggestion[] }).results;
}

function toPayload(form: TripFormState) {
  const payload: Record<string, unknown> = {
    current_location: form.current_location,
    pickup_location: form.pickup_location,
    dropoff_location: form.dropoff_location,
    start_datetime: `${form.start_datetime}:00-05:00`,
    hos_mode: form.hos_mode,
  };

  if (form.hos_mode === "quick") {
    payload.current_cycle_used_hours = form.current_cycle_used_hours;
  } else {
    payload.current_duty_status = form.current_duty_status;
    payload.current_day_driving_used_hours = form.current_day_driving_used_hours;
    payload.current_day_on_duty_used_hours = form.current_day_on_duty_used_hours;
    payload.prior_8_days = form.prior_8_days;
  }

  if (form.route_distance_miles.trim()) {
    payload.route_distance_miles = form.route_distance_miles;
  }
  if (form.average_speed_mph.trim()) {
    payload.average_speed_mph = form.average_speed_mph;
  }

  for (const key of [
    "carrier_name",
    "main_office_address",
    "truck_number",
    "trailer_number",
    "shipping_document",
  ] as const) {
    if (form[key].trim()) {
      payload[key] = form[key];
    }
  }

  return payload;
}

function readableError(data: unknown): string {
  if (!data || typeof data !== "object") {
    return "The planner could not process this trip.";
  }

  const entries = Object.entries(data as Record<string, unknown>);
  if (!entries.length) {
    return "The planner could not process this trip.";
  }

  return entries
    .map(([field, value]) => {
      if (Array.isArray(value)) {
        return `${field}: ${value.join(", ")}`;
      }
      return `${field}: ${JSON.stringify(value)}`;
    })
    .join(" ");
}
