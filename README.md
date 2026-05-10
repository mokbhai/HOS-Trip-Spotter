# HOS Trip Planner

Django + React assessment app for route planning and FMCSA property-carrier Hours of Service log generation.

## Current Status

The backend validates trip inputs and exposes an initial HOS planning endpoint.

Implemented:

- `GET /api/health/`
- `POST /api/trips/validate/`
- `POST /api/trips/plan/`

The planning endpoint resolves the submitted locations through a routing provider by default:

- Nominatim geocodes `current_location`, `pickup_location`, and `dropoff_location`
- OSRM calculates route distance, duration, turn instructions, and GeoJSON-style route coordinates
- `route_distance_miles` remains optional as a manual override for local demos and tests

The public Nominatim service requires a descriptive User-Agent and limited request volume. Set `SPOTTER_ROUTING_USER_AGENT` in deployed environments.

Planning assumptions:

- Property-carrying driver, 70 hours / 8 days
- 11-hour driving limit and 14-hour on-duty window
- 10-hour daily reset
- 34-hour cycle restart when the 70-hour cycle is exhausted
- 1 hour each for pickup and drop-off
- 30-minute fuel stops at least every 1,000 miles

## Local Development

Use the Makefile from the repository root for the normal setup and run flow.

Install Python and React dependencies:

```bash
make install
```

This creates `backend/.venv` if it does not already exist, installs
`backend/requirements.txt`, and installs the frontend dependencies with
`npm ci`.

Build the React app and start Django:

```bash
make start
```

`make start` runs the Vite production build into `backend/frontend_dist`, then
starts Django on `http://127.0.0.1:8000/`.

Runtime routing:

- `/` serves the built React frontend.
- `/api/` serves the Django REST API.
- `/static/frontend/` serves the built frontend assets.

Run tests:

```bash
make test
```

Optional manual backend workflow:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py runserver
```

Backend source lives under `backend/src`:

- `hos_planner/` contains project settings, root URLs, and frontend shell serving.
- `trips/api/` contains HTTP request handlers, API URLs, and serializers.
- `trips/services/` contains routing and HOS planning business logic.

Optional manual frontend workflow:

```bash
cd frontend
npm ci
npm run dev
```

The Vite development server proxies `/api` to `http://127.0.0.1:8000`.
For a single-port production-style run, use `make start`.
