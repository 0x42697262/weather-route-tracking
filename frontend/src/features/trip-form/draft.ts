import type { ApiUnit, Options, Place, PlaceSuggestion, SpacingChoice, Trip, TripRequest } from "@/api/types";
import { MS_PER_HOUR, MS_PER_SECOND, SECONDS_PER_MINUTE } from "@/constants";
import { API_PATH_SEPARATOR } from "@/keys";
import type { UnitSystem } from "@/lib/units";
import { formText } from "@/text";

export type PickedPlace = PlaceSuggestion;

export type TripDraft = Readonly<{
  origin: PickedPlace | null;
  destination: PickedPlace | null;
  departureLocal: string | null;
  loadValue: string;
  spacingKey: string | null;
  includeRestStops: boolean | null;
}>;

export const EMPTY_TRIP_DRAFT: TripDraft = Object.freeze({
  origin: null,
  destination: null,
  departureLocal: null,
  loadValue: "",
  spacingKey: null,
  includeRestStops: null,
});

export const TRIP_FIELDS = [
  "origin",
  "destination",
  "departure_utc",
  "load_weight",
  "checkpoint_spacing",
  "include_rest_stops",
] as const satisfies readonly (keyof TripRequest)[];

export type TripField = (typeof TRIP_FIELDS)[number];

export type FieldErrors = Readonly<Partial<Record<TripField, string>>>;

export const LOAD_UNITS: Readonly<Record<UnitSystem, ApiUnit>> = {
  imperial: "lb",
  metric: "kg",
};

const MS_PER_MINUTE = SECONDS_PER_MINUTE * MS_PER_SECOND;

export function spacingKey(choice: SpacingChoice): string {
  return `${choice.value} ${choice.unit}`;
}

export function chosenSpacing(draft: TripDraft, options: Options): SpacingChoice {
  const spacing = options.options.checkpoint_spacing;
  return spacing.choices.find((choice) => spacingKey(choice) === draft.spacingKey) ?? spacing.default;
}

export function chosenRestStops(draft: TripDraft, options: Options): boolean {
  return draft.includeRestStops ?? options.options.include_rest_stops.default;
}

export function draftUsesCustomOptions(draft: TripDraft, options: Options): boolean {
  const spacing = options.options.checkpoint_spacing;
  return (
    spacingKey(chosenSpacing(draft, options)) !== spacingKey(spacing.default) ||
    chosenRestStops(draft, options) !== options.options.include_rest_stops.default
  );
}

export type DepartureWindow = Readonly<{ earliestMs: number; latestMs: number }>;

export function departureWindow(options: Options, nowMs: number): DepartureWindow {
  const window = options.departure_window;
  return {
    earliestMs: nowMs - window.past_tolerance_minutes * MS_PER_MINUTE,
    latestMs: nowMs + window.max_hours_ahead * MS_PER_HOUR,
  };
}

export type ResolvedPlaces = Readonly<{ origin: Place | undefined; destination: Place | undefined }>;

export type DraftCheck =
  | Readonly<{ ok: true; request: TripRequest }>
  | Readonly<{ ok: false; errors: FieldErrors }>;

export function buildTripRequest(
  draft: TripDraft,
  places: ResolvedPlaces,
  options: Options,
  unitSystem: UnitSystem,
  nowIsoUtc: string,
  departureUtc: string | null,
): DraftCheck {
  const errors: Partial<Record<TripField, string>> = {};
  const load = Number(draft.loadValue);
  if (draft.loadValue.trim() === "" || !Number.isFinite(load)) {
    errors.load_weight = formText.enterLoad;
  }
  if (places.origin === undefined) {
    errors.origin = formText.pickPlace;
  }
  if (places.destination === undefined) {
    errors.destination = formText.pickPlace;
  }
  const departure = draft.departureLocal === null ? nowIsoUtc : departureUtc;
  if (departure === null) {
    errors.departure_utc = formText.enterDeparture;
  }
  if (places.origin === undefined || places.destination === undefined || departure === null || errors.load_weight) {
    return { ok: false, errors };
  }
  const spacing = chosenSpacing(draft, options);
  return {
    ok: true,
    request: {
      origin: toTripEnd(places.origin),
      destination: toTripEnd(places.destination),
      departure_utc: departure,
      load_weight: { value: load, unit: LOAD_UNITS[unitSystem] },
      checkpoint_spacing: { value: spacing.value, unit: spacing.unit },
      include_rest_stops: chosenRestStops(draft, options),
    },
  };
}

function toTripEnd(place: Place) {
  return { label: place.label, latitude: place.latitude, longitude: place.longitude };
}

export function fieldErrorsFromDetails(
  details: readonly Readonly<{ field: string; message: string }>[],
): FieldErrors {
  const errors: Partial<Record<TripField, string>> = {};
  for (const detail of details) {
    const segments = detail.field.split(API_PATH_SEPARATOR);
    const field = TRIP_FIELDS.find((candidate) => segments.includes(candidate));
    if (field !== undefined && errors[field] === undefined) {
      errors[field] = detail.message;
    }
  }
  return errors;
}

export function requestWithDefaultOptions(request: TripRequest): TripRequest {
  return {
    origin: request.origin,
    destination: request.destination,
    departure_utc: request.departure_utc,
    load_weight: request.load_weight,
  };
}

export function tripUsesCustomOptions(trip: Trip, options: Options): boolean {
  return (
    trip.options_used.checkpoint_spacing_km !== options.options.checkpoint_spacing.default.km ||
    trip.options_used.include_rest_stops !== options.options.include_rest_stops.default
  );
}
