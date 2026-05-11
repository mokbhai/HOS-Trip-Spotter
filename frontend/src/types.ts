export type HosMode = "quick" | "compliance";
export type DutyStatus = "off_duty" | "sleeper_berth" | "driving" | "on_duty";

export interface TripFormState {
  current_location: string;
  pickup_location: string;
  dropoff_location: string;
  start_datetime: string;
  hos_mode: HosMode;
  current_cycle_used_hours: string;
  route_distance_miles: string;
  average_speed_mph: string;
  carrier_name: string;
  main_office_address: string;
  truck_number: string;
  trailer_number: string;
  shipping_document: string;
  current_duty_status: DutyStatus;
  current_day_driving_used_hours: string;
  current_day_on_duty_used_hours: string;
  prior_8_days: string[];
}

export interface LocationSuggestion {
  display_name: string;
  latitude: string;
  longitude: string;
  type: string;
  importance: number | null;
}

export interface RouteInstruction {
  text: string;
  distance_miles: string;
  duration_hours: string;
}

export interface PlanRoute {
  distance_miles: string;
  average_speed_mph: string;
  estimated_drive_hours: string;
  duration_hours: string | null;
  geometry_coordinates: [number, number][];
  instructions: RouteInstruction[];
  source: "provider" | "manual";
}

export interface DutyEvent {
  status: "off_duty" | "sleeper_berth" | "driving" | "on_duty";
  kind: string;
  start_time: string;
  end_time: string;
  duration_hours: string;
  location: string;
  notes: string;
  distance_miles: string;
}

export interface DailyLogSegment {
  status: DutyEvent["status"];
  kind: string;
  start_time: string;
  end_time: string;
  duration_hours: string;
  location: string;
  notes: string;
}

export interface PaperLogRemark {
  time: string;
  location: string;
  activity: string;
  status: DutyStatus;
}

export interface PaperLogBracket {
  start_time: string;
  end_time: string;
  status: DutyStatus;
}

export interface PaperLogTotals {
  off_duty: string;
  sleeper_berth: string;
  driving: string;
  on_duty: string;
  total: string;
  working_today: string;
}

export interface PaperLog {
  remarks: PaperLogRemark[];
  brackets: PaperLogBracket[];
  totals: PaperLogTotals;
}

export interface DailyLog {
  date: string;
  segments: DailyLogSegment[];
  paper_log?: PaperLog;
}

export interface TripPlan {
  status: "planned";
  route: PlanRoute;
  events: DutyEvent[];
  daily_logs: DailyLog[];
  totals: Record<string, string>;
}
