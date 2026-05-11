import { FormEvent, useEffect, useMemo, useState } from "react";
import L from "leaflet";
import {
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  ClipboardList,
  ExternalLink,
  FileDown,
  Fuel,
  Gauge,
  Github,
  Globe2,
  LoaderCircle,
  MapPinned,
  Moon,
  Navigation,
  Route,
  Search,
  Truck,
  Youtube,
} from "lucide-react";
import { planTrip, searchLocations } from "./api";
import { trackEvent } from "./openpanel";
import type { DailyLog, DailyLogSegment, DutyEvent, LocationSuggestion, TripFormState, TripPlan } from "./types";

const defaultForm: TripFormState = {
  current_location: "Dallas, TX",
  pickup_location: "Austin, TX",
  dropoff_location: "Phoenix, AZ",
  start_datetime: "2026-05-09T08:00",
  hos_mode: "quick",
  current_cycle_used_hours: "12.5",
  route_distance_miles: "",
  average_speed_mph: "50",
  carrier_name: "Spotter Logistics",
  main_office_address: "123 Terminal Rd, Dallas, TX",
  truck_number: "TX-4821",
  trailer_number: "TR-118",
  shipping_document: "BOL-2048",
  current_duty_status: "off_duty",
  current_day_driving_used_hours: "0",
  current_day_on_duty_used_hours: "0",
  prior_8_days: ["8", "9.5", "7", "0", "10", "11", "6.25", "8"],
};

const statusLabels = {
  off_duty: "Off duty",
  sleeper_berth: "Sleeper",
  driving: "Driving",
  on_duty: "On duty",
};

const statusRows = ["off_duty", "sleeper_berth", "driving", "on_duty"] as const;

const submissionLinks = [
  {
    label: "Live app",
    href: "https://hos.mokshit.jainparichay.in/",
    icon: Globe2,
  },
  {
    label: "Demo video",
    href: "https://youtu.be/CsXG4WLkpfc?si=8i1bEWRHs8FKl1rt",
    icon: Youtube,
  },
  {
    label: "GitHub",
    href: "https://github.com/mokbhai/HOS-Trip-Spotter",
    icon: Github,
  },
] as const;

export function App() {
  const [form, setForm] = useState<TripFormState>(defaultForm);
  const [plan, setPlan] = useState<TripPlan | null>(null);
  const [error, setError] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setIsLoading(true);
    setError("");
    trackEvent("trip_plan_submitted", {
      hos_mode: form.hos_mode,
      has_route_distance_override: Boolean(form.route_distance_miles.trim()),
      has_average_speed_override: Boolean(form.average_speed_mph.trim()),
    });

    try {
      const result = await planTrip(form);
      setPlan(result);
      trackEvent("trip_plan_succeeded", {
        hos_mode: form.hos_mode,
        route_source: result.route.source,
        route_distance_miles: Number(result.route.distance_miles),
        driving_hours: Number(result.totals.driving_hours),
        events_count: result.events.length,
        daily_logs_count: result.daily_logs.length,
      });
    } catch (caught) {
      setPlan(null);
      const message = caught instanceof Error ? caught.message : "Unable to plan trip.";
      setError(message);
      trackEvent("trip_plan_failed", {
        hos_mode: form.hos_mode,
        error_type: caught instanceof Error ? caught.name : "UnknownError",
      });
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="app-shell">
      <section className="planner-panel" aria-label="Trip inputs">
        <div className="brand-lockup">
          <div className="brand-mark">
            <Truck size={24} strokeWidth={2.3} />
          </div>
          <div>
            <p>Spotter Assignment</p>
            <h1>HOS Trip Planner</h1>
          </div>
        </div>

        <form className="trip-form" id="trip-planner-form" onSubmit={handleSubmit}>
          <fieldset>
            <legend>Route</legend>
            <LocationInput
              label="Current location"
              value={form.current_location}
              onChange={(value) => setForm({ ...form, current_location: value })}
            />
            <LocationInput
              label="Pickup"
              value={form.pickup_location}
              onChange={(value) => setForm({ ...form, pickup_location: value })}
            />
            <LocationInput
              label="Drop-off"
              value={form.dropoff_location}
              onChange={(value) => setForm({ ...form, dropoff_location: value })}
            />
          </fieldset>

          <fieldset>
            <legend>Clock</legend>
            <label className="field">
              <span>Start time</span>
              <input
                type="datetime-local"
                value={form.start_datetime}
                onChange={(event) => setForm({ ...form, start_datetime: event.target.value })}
                required
              />
            </label>
            <div className="segmented-control" aria-label="HOS mode">
              <button
                type="button"
                className={form.hos_mode === "quick" ? "active" : ""}
                onClick={() => {
                  setForm({ ...form, hos_mode: "quick" });
                  trackEvent("hos_mode_selected", { mode: "quick" });
                }}
              >
                Quick
              </button>
              <button
                type="button"
                className={form.hos_mode === "compliance" ? "active" : ""}
                onClick={() => {
                  setForm({ ...form, hos_mode: "compliance" });
                  trackEvent("hos_mode_selected", { mode: "compliance" });
                }}
              >
                Compliance
              </button>
            </div>
          </fieldset>

          {form.hos_mode === "quick" ? (
            <fieldset>
              <legend>Cycle</legend>
              <NumberInput
                label="Current cycle used"
                suffix="hrs"
                value={form.current_cycle_used_hours}
                onChange={(value) => setForm({ ...form, current_cycle_used_hours: value })}
              />
            </fieldset>
          ) : (
            <fieldset>
              <legend>Compliance snapshot</legend>
              <label className="field">
                <span>Current duty status</span>
                <select
                  value={form.current_duty_status}
                  onChange={(event) =>
                    setForm({ ...form, current_duty_status: event.target.value as TripFormState["current_duty_status"] })
                  }
                >
                  <option value="off_duty">Off duty</option>
                  <option value="sleeper_berth">Sleeper berth</option>
                  <option value="driving">Driving</option>
                  <option value="on_duty">On duty</option>
                </select>
              </label>
              <div className="two-up">
                <NumberInput
                  label="Driving used"
                  suffix="hrs"
                  value={form.current_day_driving_used_hours}
                  onChange={(value) => setForm({ ...form, current_day_driving_used_hours: value })}
                />
                <NumberInput
                  label="On-duty used"
                  suffix="hrs"
                  value={form.current_day_on_duty_used_hours}
                  onChange={(value) => setForm({ ...form, current_day_on_duty_used_hours: value })}
                />
              </div>
              <div className="prior-grid" aria-label="Prior eight days">
                {form.prior_8_days.map((hours, index) => (
                  <label key={index} className="mini-field">
                    <span>D{index + 1}</span>
                    <input
                      type="number"
                      min="0"
                      max="24"
                      step="0.25"
                      value={hours}
                      onChange={(event) => {
                        const prior = [...form.prior_8_days];
                        prior[index] = event.target.value;
                        setForm({ ...form, prior_8_days: prior });
                      }}
                    />
                  </label>
                ))}
              </div>
            </fieldset>
          )}

          <fieldset>
            <legend>Routing override</legend>
            <div className="two-up">
              <NumberInput
                label="Distance"
                suffix="mi"
                value={form.route_distance_miles}
                onChange={(value) => setForm({ ...form, route_distance_miles: value })}
                required={false}
              />
              <NumberInput
                label="Avg speed"
                suffix="mph"
                value={form.average_speed_mph}
                onChange={(value) => setForm({ ...form, average_speed_mph: value })}
                required={false}
              />
            </div>
          </fieldset>

          <fieldset>
            <legend>Log sheet details</legend>
            <TextInput
              label="Carrier"
              value={form.carrier_name}
              onChange={(value) => setForm({ ...form, carrier_name: value })}
              required={false}
            />
            <TextInput
              label="Main office"
              value={form.main_office_address}
              onChange={(value) => setForm({ ...form, main_office_address: value })}
              required={false}
            />
            <div className="two-up">
              <TextInput
                label="Truck"
                value={form.truck_number}
                onChange={(value) => setForm({ ...form, truck_number: value })}
                required={false}
              />
              <TextInput
                label="Trailer"
                value={form.trailer_number}
                onChange={(value) => setForm({ ...form, trailer_number: value })}
                required={false}
              />
            </div>
            <TextInput
              label="Shipping document"
              value={form.shipping_document}
              onChange={(value) => setForm({ ...form, shipping_document: value })}
              required={false}
            />
          </fieldset>

        </form>

        <div className="planner-action-bar">
          {error ? (
            <div className="error-callout" role="alert">
              <AlertTriangle size={18} />
              <span>{error}</span>
            </div>
          ) : null}

          <button className="primary-action" type="submit" form="trip-planner-form" disabled={isLoading}>
            {isLoading ? "Planning..." : "Plan compliant trip"}
            <Navigation size={18} />
          </button>
        </div>
      </section>

      <section className="results-panel" aria-label="Trip results">
        {plan ? <TripResults plan={plan} form={form} /> : <EmptyState />}
      </section>

      <footer className="submission-footer">
        <p>Submitted as a Spotter full stack assignment by Mokshit Jain.</p>
        <nav aria-label="Submission links">
          {submissionLinks.map(({ label, href, icon: Icon }) => (
            <a
              key={href}
              href={href}
              target="_blank"
              rel="noreferrer"
              data-track="submission_link_clicked"
              data-track-label={label}
            >
              <Icon size={16} />
              <span>{label}</span>
              <ExternalLink size={13} />
            </a>
          ))}
        </nav>
      </footer>
    </main>
  );
}

function TripResults({ plan, form }: { plan: TripPlan; form: TripFormState }) {
  return (
    <>
      <section className="summary-strip" aria-label="Summary">
        <Metric icon={<Route />} label="Route miles" value={plan.route.distance_miles} />
        <Metric icon={<Gauge />} label="Drive hours" value={plan.totals.driving_hours} />
        <Metric icon={<Moon />} label="Rest hours" value={plan.totals.off_duty_hours} />
        <Metric icon={<CheckCircle2 />} label="Source" value={plan.route.source} />
      </section>

      <div className="results-grid">
        <RouteMap plan={plan} />
        <InstructionPanel plan={plan} />
      </div>

      <Timeline events={plan.events} />

      <section className="log-section">
        <div className="section-heading split-heading">
          <div>
            <CalendarClock size={20} />
            <h2>Daily log sheets</h2>
          </div>
          <button
            className="secondary-action"
            type="button"
            onClick={() => {
              trackEvent("daily_logs_printed", { daily_logs_count: plan.daily_logs.length });
              window.print();
            }}
          >
            <FileDown size={17} />
            Print logs
          </button>
        </div>
        <div className="log-stack">
          {plan.daily_logs.map((log) => (
            <DailyLogSheet key={log.date} log={log} form={form} plan={plan} />
          ))}
        </div>
      </section>
    </>
  );
}

function RouteMap({ plan }: { plan: TripPlan }) {
  const coordinates = plan.route.geometry_coordinates;
  const hasGeometry = coordinates.length > 1;

  return (
    <section className="map-panel">
      <div className="section-heading">
        <MapPinned size={20} />
        <h2>Route map</h2>
      </div>
      {hasGeometry ? <LeafletMap coordinates={coordinates} /> : <ManualMap plan={plan} />}
    </section>
  );
}

function LeafletMap({ coordinates }: { coordinates: [number, number][] }) {
  const mapId = useMemo(() => `route-map-${Math.random().toString(36).slice(2)}`, []);

  useEffect(() => {
    const element = document.getElementById(mapId);
    if (!element) {
      return undefined;
    }

    const latLngs = coordinates.map(([lon, lat]) => L.latLng(lat, lon));
    const map = L.map(element, { zoomControl: false, attributionControl: true });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);
    L.polyline(latLngs, { color: "#e2552a", weight: 5, opacity: 0.92 }).addTo(map);
    L.circleMarker(latLngs[0], { radius: 7, color: "#12312b", fillColor: "#f7c548", fillOpacity: 1 }).addTo(map);
    L.circleMarker(latLngs[latLngs.length - 1], {
      radius: 7,
      color: "#12312b",
      fillColor: "#e2552a",
      fillOpacity: 1,
    }).addTo(map);
    map.fitBounds(L.latLngBounds(latLngs), { padding: [28, 28] });

    return () => {
      map.remove();
    };
  }, [coordinates, mapId]);

  return <div id={mapId} className="leaflet-map" />;
}

function ManualMap({ plan }: { plan: TripPlan }) {
  return (
    <div className="manual-map">
      <div className="route-line" />
      <div className="pin pin-start">Start</div>
      <div className="pin pin-end">Drop</div>
      <div className="map-note">
        Manual distance override active. Provider geometry appears here when routing is used.
      </div>
      <div className="map-distance">{plan.route.distance_miles} mi</div>
    </div>
  );
}

function InstructionPanel({ plan }: { plan: TripPlan }) {
  return (
    <section className="instruction-panel">
      <div className="section-heading">
        <ClipboardList size={20} />
        <h2>Route instructions</h2>
      </div>
      {plan.route.instructions.length ? (
        <ol className="instruction-list">
          {plan.route.instructions.map((instruction, index) => (
            <li key={`${instruction.text}-${index}`}>
              <span>{instruction.text}</span>
              <small>
                {instruction.distance_miles} mi · {instruction.duration_hours} hr
              </small>
            </li>
          ))}
        </ol>
      ) : (
        <div className="quiet-box">
          Route instructions are available when the provider route is used.
        </div>
      )}
    </section>
  );
}

function Timeline({ events }: { events: DutyEvent[] }) {
  return (
    <section className="timeline-section">
      <div className="section-heading">
        <Fuel size={20} />
        <h2>Stops and duty timeline</h2>
      </div>
      <div className="timeline">
        {events.map((event, index) => (
          <article className={`timeline-card ${event.status}`} key={`${event.start_time}-${index}`}>
            <strong>{event.notes}</strong>
            <span>{statusLabels[event.status]}</span>
            <small>
              {formatTime(event.start_time)} - {formatTime(event.end_time)} · {event.duration_hours} hr
            </small>
          </article>
        ))}
      </div>
    </section>
  );
}

function DailyLogSheet({ log, form, plan }: { log: DailyLog; form: TripFormState; plan: TripPlan }) {
  const displaySegments = completeDailySegments(log);
  const computedTotals = totalHoursByStatus(displaySegments);
  const paperLog = log.paper_log;
  const paperRemarks = paperLog?.remarks;
  const miles = dailyMiles(log, plan.events);

  return (
    <article className="log-sheet">
      <div className="coded-log-sheet" aria-label={`Daily log for ${log.date}`}>
        <div className="coded-log-top">
          <BoxedCharacters label="Month / Day / Year" value={formatCompactDate(log.date)} cells={8} />
          <div className="carrier-box">
            <strong>{form.carrier_name || "Carrier"}</strong>
            <span>{form.main_office_address || "Main office address"}</span>
          </div>
          <BoxedCharacters label="Driver name" value="Driver" cells={18} />
        </div>

        <div className="coded-log-subtop">
          <BoxedCharacters label="Truck / Tractor" value={form.truck_number} cells={8} />
          <BoxedCharacters label="Trailer" value={form.trailer_number} cells={8} />
          <BoxedCharacters label="Shipping document" value={form.shipping_document} cells={12} />
          <BoxedCharacters label="Miles today" value={miles} cells={5} />
        </div>

        <div className="coded-duty-area">
          <div className="hour-labels">
            <span>Midnight</span>
            {Array.from({ length: 11 }, (_, index) => (
              <b key={index}>{index + 1}</b>
            ))}
            <span>Noon</span>
            {Array.from({ length: 11 }, (_, index) => (
              <b key={index}>{index + 1}</b>
            ))}
          </div>
          <div className="coded-duty-grid">
            <svg className="coded-duty-path" viewBox="0 0 1440 172" preserveAspectRatio="none" aria-hidden="true">
              <path d={dutyPathData(displaySegments, log.date)} />
            </svg>
            {statusRows.map((status, index) => (
              <div className="coded-duty-row" key={status}>
                <strong>
                  {index + 1}: {statusLabels[status]}
                </strong>
                <div className="coded-duty-track" />
                <b>{paperLog?.totals[status] ?? computedTotals[status].toFixed(2)}</b>
              </div>
            ))}
          </div>
        </div>

        <div className="coded-remarks">
          <strong>Remarks</strong>
          {paperRemarks
            ? paperRemarks.map((remark, index) => (
                <p key={`${remark.time}-${index}`}>{paperRemarkText(remark.time, remark.location, remark.activity)}</p>
              ))
            : log.segments.map((segment, index) => (
                <p key={`${segment.start_time}-${index}`}>
                  {formatTime(segment.start_time)} - {formatTime(segment.end_time)}: {segment.notes}
                </p>
              ))}
        </div>

        <div className="coded-log-footer">
          <BoxedCharacters label="Total miles driving today" value={miles} cells={5} />
          <div className="signature-line">
            <span>Driver signature</span>
          </div>
          <aside className="recap-sidebar">
            <strong>70 hours / 8 days</strong>
            <span>{plan.totals.driving_hours} driving</span>
            <span>{plan.totals.on_duty_hours} on duty</span>
            <span>{plan.totals.off_duty_hours} off duty</span>
          </aside>
        </div>
      </div>
      <div className="screen-log-summary">
        <strong>Remarks</strong>
        {paperRemarks
          ? paperRemarks.map((remark, index) => (
              <p key={`${remark.time}-${index}`}>{paperRemarkText(remark.time, remark.location, remark.activity)}</p>
            ))
          : log.segments.map((segment, index) => (
              <p key={`${segment.start_time}-${index}`}>
                {formatTime(segment.start_time)} - {formatTime(segment.end_time)}: {segment.notes}
                {segment.location ? ` (${segment.location})` : ""}
              </p>
            ))}
      </div>
    </article>
  );
}

function BoxedCharacters({ label, value, cells }: { label: string; value: string; cells: number }) {
  const chars = value.replace(/[-/\s]/g, "").slice(0, cells).split("");
  return (
    <div className="boxed-characters">
      <div className="character-cells" style={{ gridTemplateColumns: `repeat(${cells}, 1fr)` }}>
        {Array.from({ length: cells }, (_, index) => (
          <span key={index}>{chars[index] || ""}</span>
        ))}
      </div>
      <em>{label}</em>
    </div>
  );
}

function Metric({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <article className="metric">
      {icon}
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function EmptyState() {
  return (
    <div className="empty-state">
      <Truck size={44} />
      <h2>Plan a route to generate map, stops, and logs.</h2>
      <p>
        Use the distance override for repeatable local demos, or clear it to call the backend routing provider.
      </p>
    </div>
  );
}

function TextInput({
  label,
  value,
  onChange,
  required = true,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input value={value} onChange={(event) => onChange(event.target.value)} required={required} />
    </label>
  );
}

function LocationInput({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  const [suggestions, setSuggestions] = useState<LocationSuggestion[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const inputId = useMemo(() => `${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-location-input`, [label]);
  const listboxId = `${inputId}-results`;
  const canSearch = value.trim().length >= 3;

  useEffect(() => {
    const query = value.trim();
    if (query.length < 3) {
      setSuggestions([]);
      setSearchError("");
      setIsSearching(false);
      return undefined;
    }

    const controller = new AbortController();
    const timeout = window.setTimeout(() => {
      setIsSearching(true);
      setSearchError("");
      searchLocations(query, controller.signal)
        .then((results) => {
          setSuggestions(results);
          setIsOpen(document.activeElement?.id === inputId);
        })
        .catch((caught) => {
          if (controller.signal.aborted) {
            return;
          }
          setSuggestions([]);
          setSearchError(caught instanceof Error ? caught.message : "Could not search locations.");
        })
        .finally(() => {
          if (!controller.signal.aborted) {
            setIsSearching(false);
          }
        });
    }, 350);

    return () => {
      controller.abort();
      window.clearTimeout(timeout);
    };
  }, [inputId, value]);

  return (
    <label className="field location-field">
      <span>{label}</span>
      <div className="location-search">
        <Search className="location-search-icon" size={16} aria-hidden="true" />
        <input
          id={inputId}
          value={value}
          onChange={(event) => {
            onChange(event.target.value);
            setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
          onBlur={() => {
            window.setTimeout(() => setIsOpen(false), 120);
          }}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={isOpen && canSearch}
          aria-controls={listboxId}
          required
        />
        {isSearching ? <LoaderCircle className="location-search-loader" size={16} aria-hidden="true" /> : null}
        {isOpen && canSearch ? (
          <div className="location-results" id={listboxId} role="listbox">
            {searchError ? <p className="location-result-note">{searchError}</p> : null}
            {!searchError && !isSearching && suggestions.length === 0 ? (
              <p className="location-result-note">No matching locations.</p>
            ) : null}
            {suggestions.map((suggestion) => (
              <button
                key={`${suggestion.latitude}-${suggestion.longitude}-${suggestion.display_name}`}
                type="button"
                role="option"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => {
                  onChange(suggestion.display_name);
                  setIsOpen(false);
                  trackEvent("location_suggestion_selected", { field: label, type: suggestion.type });
                }}
              >
                <strong>{primaryLocationName(suggestion.display_name)}</strong>
                <small>{secondaryLocationName(suggestion.display_name)}</small>
              </button>
            ))}
          </div>
        ) : null}
      </div>
    </label>
  );
}

function NumberInput({
  label,
  suffix,
  value,
  onChange,
  required = true,
}: {
  label: string;
  suffix: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <div className="number-field">
        <input
          type="number"
          min="0"
          step="0.25"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          required={required}
        />
        <em>{suffix}</em>
      </div>
    </label>
  );
}

function hourOfDay(value: string) {
  const time = value.match(/T(\d{2}):(\d{2})/);
  if (!time) {
    return 0;
  }
  return Number(time[1]) + Number(time[2]) / 60;
}

function primaryLocationName(displayName: string) {
  return displayName.split(",")[0]?.trim() || displayName;
}

function secondaryLocationName(displayName: string) {
  const parts = displayName.split(",").map((part) => part.trim()).filter(Boolean);
  return parts.slice(1, 4).join(", ");
}

function dutyPathData(segments: DailyLogSegment[], logDate: string) {
  const sortedSegments = [...segments].sort((left, right) =>
    left.start_time.localeCompare(right.start_time),
  );
  const commands: string[] = [];
  let currentX = 0;
  let currentY = 0;

  for (const segment of sortedSegments) {
    const startX = minuteInLogDay(segment.start_time, logDate);
    const endX = minuteInLogDay(segment.end_time, logDate);
    const y = dutyRowY(segment.status);

    if (endX <= startX) {
      continue;
    }

    if (!commands.length) {
      commands.push(`M ${startX} ${y}`);
    } else {
      if (currentX !== startX) {
        commands.push(`H ${startX}`);
      }
      if (currentY !== y) {
        commands.push(`V ${y}`);
      }
    }

    commands.push(`H ${endX}`);
    currentX = endX;
    currentY = y;
  }

  return commands.join(" ");
}

function dutyRowY(status: DailyLogSegment["status"]) {
  const rowIndex = statusRows.indexOf(status);
  return rowIndex * 43 + 21.5;
}

function formatTime(value: string) {
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  if (!match) {
    return value;
  }

  const [, , month, day, hour, minute] = match;
  const monthName = new Intl.DateTimeFormat(undefined, { month: "short" }).format(
    new Date(Number(match[1]), Number(month) - 1, Number(day)),
  );
  return `${monthName} ${Number(day)}, ${hour}:${minute}`;
}

function formatRemarkTime(value: string) {
  const isoTime = value.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  if (isoTime) {
    return formatTime(value);
  }

  const clockTime = value.match(/^(\d{1,2}):(\d{2})/);
  if (clockTime) {
    return `${clockTime[1].padStart(2, "0")}:${clockTime[2]}`;
  }

  return value;
}

function paperRemarkText(time: string, location: string, activity: string) {
  return `${formatRemarkTime(time)}: ${location} - ${activity}`;
}

function formatLogDate(value: string) {
  const [year, month, day] = value.split("-");
  return `${month}/${day}/${year}`;
}

function formatCompactDate(value: string) {
  const [year, month, day] = value.split("-");
  return `${month}${day}${year}`;
}

function totalHoursByStatus(segments: DailyLogSegment[]) {
  return statusRows.reduce(
    (totals, status) => {
      totals[status] = segments
        .filter((segment) => segment.status === status)
        .reduce((sum, segment) => sum + Number(segment.duration_hours), 0);
      return totals;
    },
    {
      off_duty: 0,
      sleeper_berth: 0,
      driving: 0,
      on_duty: 0,
    } as Record<(typeof statusRows)[number], number>,
  );
}

function dailyMiles(log: DailyLog, events: DutyEvent[]) {
  const miles = events
    .filter((event) => event.start_time.slice(0, 10) === log.date && event.status === "driving")
    .reduce((sum, event) => sum + Number(event.distance_miles), 0);
  return miles.toFixed(0);
}

function completeDailySegments(log: DailyLog): DailyLogSegment[] {
  const sortedSegments = [...log.segments].sort((left, right) =>
    left.start_time.localeCompare(right.start_time),
  );
  const completed: DailyLogSegment[] = [];
  let cursorMinutes = 0;

  for (const segment of sortedSegments) {
    const startMinutes = minuteInLogDay(segment.start_time, log.date);
    const endMinutes = minuteInLogDay(segment.end_time, log.date);

    if (startMinutes > cursorMinutes) {
      completed.push(offDutyGap(log.date, cursorMinutes, startMinutes));
    }

    completed.push(segment);
    cursorMinutes = Math.max(cursorMinutes, endMinutes);
  }

  if (cursorMinutes < 24 * 60) {
    completed.push(offDutyGap(log.date, cursorMinutes, 24 * 60));
  }

  return completed;
}

function offDutyGap(date: string, startMinutes: number, endMinutes: number): DailyLogSegment {
  return {
    status: "off_duty",
    kind: "off_duty_gap",
    start_time: timeForMinute(date, startMinutes),
    end_time: timeForMinute(date, endMinutes),
    duration_hours: ((endMinutes - startMinutes) / 60).toFixed(2),
    location: "",
    notes: "Off-duty time not otherwise assigned",
  };
}

function minuteInLogDay(value: string, logDate: string) {
  const match = value.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})/);
  if (!match) {
    return 0;
  }

  const [, date, hour, minute] = match;
  if (date < logDate) {
    return 0;
  }
  if (date > logDate) {
    return 24 * 60;
  }

  return Math.min(Number(hour) * 60 + Number(minute), 24 * 60);
}

function timeForMinute(date: string, totalMinutes: number) {
  const clampedMinutes = Math.max(0, Math.min(totalMinutes, 24 * 60));
  const hour = Math.floor(clampedMinutes / 60);
  const minute = clampedMinutes % 60;
  return `${date}T${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}:00`;
}
