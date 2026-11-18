export const appText = {
  documentTitle: "Weather routes",
  mapLabel: "Map",
  openMeteoAttribution: "Weather data by Open-Meteo.com",
} as const;

export const configText = {
  invalidVariable: (variableName: string, problem: string) =>
    `Invalid public config ${variableName}: ${problem}`,
} as const;

export const bootText = {
  missingRootElement: (elementId: string) => `Missing root element #${elementId}`,
  missingProvider: (providerName: string) => `Missing ${providerName} above this component`,
} as const;

export const sheetText = {
  title: "Trip",
  panelLabel: "Trip panel",
  changeHeight: "Change panel height",
  planTrip: "Plan a trip",
  planTripHint: "Enter where you start, where you are going and when you leave.",
  routes: "Routes",
  routeTitle: (routeName: string) => routeName,
} as const;

export const levelText = {
  legendTitle: "Risk levels",
  unknown: "Unknown",
  ferry: "Ferry",
  levels: {
    low: "Low",
    moderate: "Moderate",
    high: "High",
    severe: "Severe",
    no_travel: "No Travel",
  },
  riskSuffix: (levelLabel: string) => `${levelLabel} risk`,
} as const;

export const sliderText = {
  label: "Forecast hour",
  unavailableHint: "Plan a trip to move through the forecast.",
  hourOffset: (hour: number) => `+${hour} h`,
} as const;

export const heatmapText = {
  label: "Heatmap layer",
  unavailableHint: "The heatmap appears after a trip is planned.",
  loading: "Loading the weather heatmap…",
  failed: "The weather heatmap is not available. Routes are not affected.",
  cellsMissing: (count: number) => `${count} heatmap cells have no forecast.`,
  legend: "Legend",
  layers: {
    combined_risk: "Risk",
    wind_speed: "Wind",
    rain_rate: "Rain",
    snowfall_rate: "Snow",
  } as Readonly<Record<string, string>>,
} as const;

export const preferencesText = {
  openSettings: "Settings",
  title: "Settings",
  unitsLabel: "Units",
  mapStyleLabel: "Map style",
  units: {
    imperial: "Imperial (mi, mph, lb)",
    metric: "Metric (km, km/h, kg)",
  },
  mapStyles: {
    configured: "Standard",
  },
} as const;

export const unitText = {
  mile: "mi",
  kilometer: "km",
  milePerHour: "mph",
  kilometerPerHour: "km/h",
  inchPerHour: "in/h",
  millimeterPerHour: "mm/h",
  centimeterPerHour: "cm/h",
  pound: "lb",
  kilogram: "kg",
} as const;

export const durationText = {
  hoursAndMinutes: (hours: number, minutes: number) => `${hours} h ${minutes} m`,
  minutesOnly: (minutes: number) => `${minutes} m`,
} as const;

export const apiText = {
  unexpectedError: "Something went wrong. Try again.",
  networkError: "The server could not be reached. Check the connection and try again.",
} as const;

export const formText = {
  origin: "From",
  destination: "To",
  placePlaceholder: "City or address",
  placeHint: (minChars: number) => `Type at least ${minChars} characters, then pick a place.`,
  placeSearching: "Searching…",
  placeNoResults: "No places found.",
  placeLoading: "Getting the place…",
  departure: "Departure",
  departureHint: (zoneName: string) => `Your time zone (${zoneName}).`,
  loadWeight: "Load weight",
  spacing: "Checkpoint spacing",
  advanced: "Advanced options",
  restStops: "Add rest stops",
  restStopsHint: "A 30-minute break after 8 hours of driving, 10 hours off after 11 hours or a 14-hour shift.",
  defaultSuffix: (label: string) => `${label} (default)`,
  submit: "Find routes",
  submitting: "Finding routes…",
  customOptions: "Custom options in use",
  resetDefaults: "Reset to defaults",
  pickPlace: "Pick a place from the list.",
  enterLoad: "Enter the load weight.",
  enterDeparture: "Enter the departure date and time.",
  placeFailed: "This place could not be loaded. Pick it again.",
} as const;

export const routeText = {
  name: (letter: string) => `Route ${letter}`,
  rank: (rank: number) => `#${rank}`,
  recommended: "Recommended",
  bestAvailable: "Best available",
  selected: "Selected",
  details: "Details",
  showDetails: (routeName: string) => `Details of ${routeName}`,
  backToRoutes: "All routes",
  editTrip: "Edit trip",
  sources: {
    fastest: "Fastest",
    alternative: "Alternative",
    avoid_tolls: "Avoids tolls",
    avoid_highways: "Avoids highways",
    detour: "Detour",
    similar: "Similar route",
    slower: "Slower route",
  },
  travelTime: "Travel time",
  distance: "Distance",
  arrival: "Arrives",
  restAdded: (duration: string) => `Includes ${duration} of rest`,
  levelDistances: "Distance at each risk level",
  warnings: {
    unknown_weather: (distances: RouteWarningDistances) =>
      `${distances.unknown} has no forecast and is not rated.`,
    ferry_crossing: (distances: RouteWarningDistances) =>
      `Includes ${distances.ferry} by ferry. Check the sailing with the ferry operator.`,
    has_blocking_level: (distances: RouteWarningDistances) => `${distances.blocking} where travel is not advised.`,
  },
  notRecommendable: {
    no_known_weather: "Not recommended: no forecast for this route.",
    blocked: "Not recommended: it has stretches where travel is not advised.",
    too_much_unknown_weather: "Not recommended: too much of this route has no forecast.",
  },
  tripWarnings: {
    gross_weight_over_limit: () => "The truck with this load is over the federal gross weight limit.",
    fewer_routes_than_target: (context: TripWarningContext) =>
      `Only ${context.routesFound} routes found for this trip.`,
    weather_partial: () => "Some forecasts are missing; those checkpoints are Unknown.",
    weather_unavailable: () => "No forecast could be loaded; every level is Unknown.",
  },
  checkpoints: "Checkpoints",
  checkpointTitle: (index: number) => `Checkpoint ${index + 1}`,
  atDistance: (distance: string) => `at ${distance}`,
  onFerry: "On a ferry",
  decidedBy: "Decided by",
  decidedByKinds: {
    band: (variableLabel: string) => `${variableLabel} at this level`,
    load_rule: (variableLabel: string) => `${variableLabel} with this load`,
  } as Readonly<Record<string, (variableLabel: string) => string>>,
  decidedByNothing: "Every condition at the lowest level",
  decidedByUnknown: "No forecast for this time and place",
  noValue: "No data",
  stops: "Rest stops",
  stopKinds: {
    break: "Break",
    off_duty: "Off duty",
  },
  stopLine: (kindLabel: string, start: string, duration: string) => `${kindLabel} at ${start} for ${duration}`,
  restAssumptions:
    "Rest assumes the driver starts rested, with no loading or fueling time; weekly limits are not modeled.",
  basis: "How this was computed",
  ruleSetVersion: (version: number) => `Rule set version ${version}`,
  spacingUsed: (spacing: string) => `Checkpoints every ${spacing}`,
  loadUsed: (load: string) => `Load ${load}`,
  restUsed: (included: boolean) => (included ? "Rest stops included" : "No rest stops"),
  closeCheckpoint: "Close",
} as const;

export type TripWarningContext = Readonly<{ routesFound: number }>;

export type RouteWarningDistances = Readonly<{ unknown: string; ferry: string; blocking: string }>;

export const variableText = {
  wind_speed: "Wind",
  rain_rate: "Rain",
  snowfall_rate: "Snow",
} as const;

export const verdictText = {
  planTrip: "Plan a trip",
  finding: "Finding routes…",
  take: (routeName: string) => `Take ${routeName}`,
  noRecommendation: {
    every_route_blocked: "No safe route: every route has No Travel stretches",
    no_known_weather: "No recommendation: no forecast could be loaded for these routes",
    too_much_unknown_weather: "No recommendation: too much of each usable route has no forecast",
  },
  bestAvailablePrefix: {
    every_route_blocked: "No safe route",
    no_known_weather: "No forecast",
    too_much_unknown_weather: "Forecast incomplete",
  },
  bestAvailable: (routeName: string) => `best available is ${routeName}`,
  failed: (message: string) => `No routes: ${message}`,
  separator: " · ",
  unknownPart: (distance: string) => `${distance} unknown`,
} as const;
