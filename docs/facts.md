# Facts

What has been checked about third parties and tools, and what still needs checking. Facts come from
primary sources: live requests, vendor documentation, official terms, regulations. Each fact below
was read from the page named, on the date given.

## Confirmed

### Routing and geocoding

| ID | Fact | Source | Consequence |
|---|---|---|---|
| F-1 | The public OSRM demo server, asked for 3 alternatives, returned 1 route for Dallas to Oklahoma City (330 km) and 2 routes for Chicago to Denver (1,618 km and 1,793 km) | Live requests to `router.project-osrm.org`, 2026-11-16 | A provider can return fewer routes than asked. The app handles 1 to 3 routes and says when there are fewer than 3 |
| F-3 | Mapbox Directions has 4 profiles: `driving-traffic`, `driving`, `walking`, `cycling`. No truck profile | `docs.mapbox.com/api/navigation/directions/`, 2026-11-16 | Drive times are car times. Truck speed is modeled by this app (`trip-planning.md`) |
| F-4 | Mapbox Directions accepts `max_height`, `max_width` (meters) and `max_weight` (metric tons, default 2.5, up to 100) on the driving profiles. They exclude roads by posted restriction and do not change speeds. Coverage "may vary by region" | Same page | The adapter can pass the load weight to avoid weight-restricted roads |
| F-5 | The API page says both "Up to two alternatives may be returned" and "The response object may contain at most two routes". Mapbox's own SDKs say 2 in total: Swift `RouteResponse.swift` "contains a maximum of two `Route`s"; Java `DirectionsResponse.java` "At most this will return 2" | Same page; `mapbox/mapbox-directions-swift` and `mapbox/mapbox-java` sources, 2026-11-16 | Expect at most 2 routes per request, so reaching 3 almost always needs a top-up round (`adr/0010`). Parsing must not assume a fixed count |
| F-6 | `annotations` gives per-segment `distance`, `duration` and `speed` between each pair of coordinates, and "must be used in conjunction with `overview=full`" | Same page | Arrival times and the truck speed cap can be computed per segment |
| F-7 | Mapbox Directions limits: 300 requests per minute, 25 coordinates, 10,000 km total distance on driving profiles | Same page | Bounds for the adapter and for maximum trip distance |
| F-8 | Mapbox Product Terms 2.10.1: "Customer shall not export, download, cache or store results from any request to a Navigation API." | Product Terms PDF, "Last Updated: October 20, 2026", from `mapbox.com/legal/product-terms` | Route results from Mapbox must not be cached or stored on the server |
| F-9 | Mapbox Product Terms 2.7.2: "Customer shall not export, store, or cache Temporary Geocodes." Permanent geocodes may be stored and need the `permanent=true` parameter | Same PDF; `docs.mapbox.com/api/search/geocoding/` | Place suggestions must not be cached unless requested as permanent |
| F-10 | Mapbox Product Terms 1.2.2: an application "related to vehicle usage" needs an additional license, and vehicle usage includes "applications primarily intended for use within vehicles". 1.2.1 excludes such applications from free non-production use | Same PDF | An app for truck drivers plausibly needs a paid Mapbox license, even in development. The first version proceeds on Mapbox; settle this before commercial use (`adr/0002`) |
| F-25 | Mapbox Directions `exclude` accepts `motorway`, `toll` and `ferry` on the driving profiles. An alternative route "does not exist in all circumstances" | Same page as F-3 | Avoiding tolls and avoiding highways are available as top-up rounds |
| F-39 | Mapbox pricing: Directions 100,000 requests a month free, then $2.00 per 1,000; Temporary Geocoding 100,000 free, then $0.75 per 1,000. Without a payment method, trial caps apply instead: 10,000 Directions and 10,000 Temporary Geocoding requests a month | `mapbox.com/pricing`; `docs.mapbox.com/accounts/guides/signup.md`, 2026-11-16 | A trip costs 1 to 5 Directions requests (`ROUTE_MAX_EXTRA_REQUESTS`), so the trial cap covers about 2,000 trips a month |
| F-11 | Truck routing with vehicle weight and height is documented for TomTom (`travelMode=truck`, `vehicleWeight`), HERE (`transportMode=truck`, `vehicle[grossWeight]`), OpenRouteService (`driving-hgv`), Valhalla (`truck` costing) and GraphHopper (custom model) | Each vendor's routing documentation, 2026-11-16 | TomTom, HERE and OpenRouteService are the named alternatives for a second routing adapter (`adr/0002`). Their terms and prices are not checked yet |

### Truck speed

| ID | Fact | Source | Consequence |
|---|---|---|---|
| F-40 | TomTom Routing: 20,000 requests a month free, no card needed; `maxAlternatives` 0 to 5 | `developer.tomtom.com/pricing`; calculate-route docs, 2026-11-16 | A single request can return 3 routes. Commercial use and caching terms are unverified (V-17) |
| F-41 | HERE Routing v8: truck routing 5,000 transactions a month free, then $2.92 per 1,000 (car 30,000 free); up to 6 alternatives besides the optimal route. Results may not be cached or stored "for more than 30 days", and otherwise only as HTTP caching headers allow | HERE pricing data behind the pricing page; `docs.here.com` calculateroutes reference; HERE Platform Terms (effective 2023-09-18) | A single request can return 3 truck routes. Caching up to 30 days is allowed |
| F-42 | OpenRouteService free plan: 2,000 directions requests a day, 40 a minute, including `driving-hgv`. Results are CC-BY-SA 4.0 and attribution is required. The engine is GPL v3 and self-hostable; a self-hosted instance allows 3 alternative routes by default | `account.heigit.org` plan and terms data; `GIScience/openrouteservice` sources and docs | Self-hosting removes quota limits. The hosted API's alternative limit and commercial terms are unverified (V-17) |
| F-12 | 8 US states post a lower rural-interstate limit for trucks, e.g. California "70; trucks: 55", Washington "trucks: 60", Michigan "70 (65 trucks)" | IIHS speed limit table dated November 2026, `iihs.org/topics/speed/speed-limit-laws` | Trucks are slower than car routing times in some states; a single factor cannot capture this exactly |
| F-13 | Fleets voluntarily set speed limiters "most often at speeds from 60 to 70 mph". The proposed federal rule considered 60, 65 and 68 mph and was withdrawn in July 2025 | Federal Register documents 2016-20934 and 2025-13928 | Basis for a default truck speed cap. There is no federal mandate |
| F-14 | Measured average truck speeds on five interstate corridors in 2005 were 50 to 58 mph | FHWA-HOP-07-071, `ops.fhwa.dot.gov` | Old data; supports that trucks average well under the posted car limit |
| F-15 | A routing engine's own truck example: "for faster roads the truck should be 10% slower and the maximum should be 100km/h" | GraphHopper `docs/core/custom-models.md` | Precedent for the model used here: a factor plus a speed cap |

### Driving and rest rules (United States, property-carrying drivers)

| ID | Fact | Source | Consequence |
|---|---|---|---|
| F-16 | "A driver may not drive without first taking 10 consecutive hours off duty" | 49 CFR 395.3(a)(1), eCFR, current as of 2026-11-12 | Default off-duty length |
| F-17 | "A driver may not drive after a period of 14 consecutive hours after coming on-duty" | 395.3(a)(2) | Default shift window |
| F-18 | "A driver may drive a total of 11 hours during the period specified in paragraph (a)(2)" | 395.3(a)(3)(i) | Default driving limit per shift |
| F-19 | "driving is not permitted if more than 8 hours of driving time have passed without at least a consecutive 30-minute interruption in driving status" | 395.3(a)(3)(ii) | Default break rule; it counts driving time, not on-duty time |
| F-20 | On duty at most 60 hours in 7 consecutive days, or 70 hours in 8 | 395.3(b) | Not modeled in the first version |
| F-21 | Adverse driving conditions allow "not more than two additional hours", and are defined as conditions "not known, or could not reasonably be known" before the duty day | 395.1(b)(1), 395.2 | Not modeled. Forecast weather known before departure likely does not qualify (an inference, not a quote) |

### Map tiles

| ID | Fact | Source | Consequence |
|---|---|---|---|
| F-22 | OpenFreeMap: "no limits on the number of map views or requests", "no API keys", "Is commercial usage allowed? Yes." Attribution is required. Style URL `https://tiles.openfreemap.org/styles/liberty`. It "may discontinue it at any time without notice" | `openfreemap.org`, its quick start and terms (updated October 14, 2026) | Chosen tile source. No uptime promise, so the style URL is a setting |
| F-23 | MapTiler's free plan is "limited to non-commercial use"; Stadia's free plan says "Commercial use not allowed"; Protomaps' hosted API is free for non-commercial use | Each vendor's pricing or terms page, 2026-11-16 | Not chosen as the default |
| F-24 | Mapbox Product Terms: map-load pricing requires a "Qualified Renderer", defined as Mapbox GL JS; Studio styles may be used only "on a Mapbox Map" | Product Terms 2.8.3, 3.57, 2.11 | Mapbox tiles are not used with MapLibre |

### Libraries

| ID | Fact | Source | Consequence |
|---|---|---|---|
| F-33 | `react-map-gl` 8.1.3 exports `./maplibre` (`import Map from 'react-map-gl/maplibre'`) and accepts `maplibre-gl >=1.13.0`. MapLibre's style spec has `heatmap` and `circle` layers; its map has `setPaintProperty`, `setFilter` and `setFeatureState` | npm registry; `visgl/react-map-gl` README; `maplibre/maplibre-style-spec` v8.json; `maplibre-gl-js` `src/ui/map.ts` | The slider can switch the hour through paint, filter or feature state without new data (V-12 still needs a measurement) |
| F-34 | Vaul's README: "This repo is unmaintained." Last release 1.1.2, 2024-12-14. shadcn's Drawer uses Vaul only on its Radix base; on its Base UI base it uses `@base-ui/react/drawer`, whose `DrawerRoot` has `snapPoints`, `snapPoint`, `defaultSnapPoint` and `onSnapPointChange`. `@base-ui/react` 1.9.0, released 2026-10-09, MIT | `emilkowalski/vaul` README; `shadcn-ui/ui` registry sources; npm registry; `mui/base-ui` `packages/react/src/drawer/root/DrawerRoot.tsx` | The frontend is created on shadcn's Base UI base; Vaul is not used |
| F-35 | shadcn's `components.json` uses `"components": "@/components"` and `"utils": "@/lib/utils"` | `shadcn-ui/ui` `apps/v4/content/docs/(root)/components-json.mdx` | Generated components already follow the no-relative-imports rule |
| F-36 | Django Ninja 1.8.0 supports async views, serves its OpenAPI document at `openapi.json` relative to where the API is mounted, and emits OpenAPI 3.1.0. `openapi-typescript` "Supports OpenAPI 3.0 and 3.1". Django 6.1.3 supports Python 3.12 to 3.15 | `vitalik/django-ninja` docs and `ninja/main.py`, `ninja/openapi/schema.py`; `openapi-ts` README; Django FAQ and PyPI | Mount the API at `api/` so the document is at `/api/openapi.json`. Python 3.14 with Django 6.1 |
| F-37 | Ruff has `TID252` (relative imports), `PLR2004` (magic value comparison), `ban-relative-imports = "all"` and `banned-api` | `docs.astral.sh/ruff` rules and settings pages | The lint rules in `engineering-guidelines.md` sections 4.2, 4.3 and 4.6 exist as written |
| F-38 | `httpx` has not released since 0.28.1 (2024-12-06); its repository is active and not archived | PyPI; GitHub API | Still used. The transport-injection design means it can be replaced in the adapters only |

### Weather

| ID | Fact | Source | Consequence |
|---|---|---|---|
| F-2 | `api.open-meteo.com` does not accept connections from the development machine: 8 IPv4 attempts timed out on connect, while `open-meteo.com` loads. The host has no IPv6 record | `curl`, 2026-11-16 | Not yet proven reachable from anywhere. Check from another network and from the deployment host (V-10). Adapter tests use recorded responses |
| F-26 | Hourly units by default: `wind_speed_10m` km/h, `wind_gusts_10m` km/h, `rain`, `showers` and `precipitation` mm, `snowfall` cm. `wind_speed_unit` accepts `kmh`, `ms`, `mph`, `kn`; `precipitation_unit` accepts `mm`, `inch` | `open-meteo.com/en/docs`, 2026-11-16 | Request the defaults; they are already the server's metric units (`adr/0001`) |
| F-27 | `wind_speed_10m` is the instant value at the timestamp. `rain`, `showers`, `snowfall` and `precipitation` are sums "of the preceding hour". `precipitation` includes snow. Gusts are the "maximum of the preceding hour" | Same page | An hourly sum is the rate in mm/h or cm/h. Rain rate = `rain` + `showers`, not `precipitation` (which would count snow twice). Which hour to read differs by variable (`trip-planning.md`) |
| F-28 | `forecast_days` is 0 to 16, default 7; `forecast_hours` has no stated maximum. Times are GMT by default; `timeformat=unixtime` gives seconds since 1970 UTC | Same page | 48 hours from any departure within the next 14 days is inside the range. Request GMT |
| F-29 | The default "best match" uses the highest-resolution model available per variable and hour; for North America that includes NOAA RRFS (3 km, 84 hours), with GFS (about 13 km) beyond. Returned coordinates are the center of the grid cell. HRRR is "discontinued end of November 2026" | `open-meteo.com/en/docs`, `/en/docs/gfs-api` | Resolution is finer in the first 84 hours. Cache cells by the coordinates the API returns, not by the requested ones |
| F-30 | Several locations per request: comma-separated `latitude` and `longitude`. The free API allows up to 1000 locations per request (source code default, not in the docs). Each location costs at least one API call | `open-meteo.com/en/docs`; `open-meteo/open-meteo` source, commit be287f3 | Batching saves round trips, not quota. The quota decides how many weather cells a trip may use |
| F-31 | Free API: "Less than 10'000 API calls per day, 5'000 per hour and 600 per minute", for "non-commercial purposes" only. Paid plans use `customer-api.open-meteo.com` with an `apikey` | `open-meteo.com/en/terms`, `/en/pricing` | Fine for the first version. The base URL and key are settings. Commercial use needs a paid plan |
| F-32 | Data are CC BY 4.0. "You must include a link next to any location Open-Meteo data are displayed", e.g. "Weather data by Open-Meteo.com" | `open-meteo.com/en/licence` | The map shows this attribution with the heatmap and checkpoint details |

## To verify

UNVERIFIED. Each is a belief from memory until checked. "Needed before" names what must wait for
the check.

| ID | Claim to check | Needed before |
|---|---|---|
| V-1 | A live Mapbox request confirms at most 2 routes (F-5); on 5 real trips, which top-up rounds were needed to reach 3 | Routing work |
| V-9 | Whether Open-Meteo's terms allow caching responses. Its terms, pricing, licence and docs pages say nothing about it | Weather work |
| V-10 | Open-Meteo is reachable from another network and from the deployment host, and a live response matches F-26 to F-29 | Weather work |
| V-12 | MapLibre heatmap or circle layers can switch the displayed hour without re-uploading data, at a smooth frame rate on a phone | The heatmap |
| V-16 | Caddy obtains a certificate for the subdomain once the DNS record exists | First deploy |
| V-17 | TomTom's commercial-use and caching terms; HERE's free-plan commercial use; OpenRouteService's hosted alternative limit and commercial terms. Their pages render with JavaScript and need a browser | Before a second routing adapter |

When a claim is checked, move it to Confirmed with its source and date, or record what turned out
to be different and what that changes.
