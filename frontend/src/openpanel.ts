import { OpenPanel } from "@openpanel/web";

const clientId = import.meta.env.VITE_OPENPANEL_CLIENT_ID;
const disabled = import.meta.env.VITE_OPENPANEL_DISABLED === "true" || !clientId;

export const openpanel = new OpenPanel({
  clientId: clientId || "disabled",
  apiUrl: import.meta.env.VITE_OPENPANEL_API_URL || "https://api.openpanel.dev",
  disabled,
  trackScreenViews: true,
  trackOutgoingLinks: true,
  trackAttributes: true,
});

openpanel.setGlobalProperties({
  app: "hos_trip_planner",
  assignment: "spotter_full_stack",
});

export function trackEvent(name: string, properties?: Record<string, unknown>) {
  if (disabled) {
    return;
  }

  try {
    void openpanel.track(name, properties).catch(() => {
      // Analytics should never interrupt trip planning.
    });
  } catch {
    // Analytics should never interrupt trip planning.
  }
}
