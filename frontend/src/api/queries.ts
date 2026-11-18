import { queryOptions, skipToken, useQuery, type UseQueryResult } from "@tanstack/react-query";
import { useMemo } from "react";
import { apiClient, unwrap } from "@/api/client";
import type { ApiRequestError } from "@/api/errors";
import type {
  Options,
  Place,
  PlaceSuggestion,
  Trip,
  TripRequest,
  WeatherGrid,
  WeatherGridRequest,
} from "@/api/types";
import { OPTIONS_STALE_TIME_MS, PLACE_QUERY_MIN_CHARS, SERVER_DATA_STALE_TIME_MS } from "@/constants";
import { QUERY_KEYS } from "@/keys";
import { useUiState } from "@/state/context";

declare module "@tanstack/react-query" {
  interface Register {
    defaultError: ApiRequestError;
  }
}

const NO_SUGGESTIONS: readonly PlaceSuggestion[] = [];

export const optionsQuery = queryOptions({
  queryKey: [QUERY_KEYS.options],
  queryFn: ({ signal }) => unwrap(apiClient.GET("/api/v1/options", { signal })),
  staleTime: OPTIONS_STALE_TIME_MS,
});

export function useOptions(): UseQueryResult<Options, ApiRequestError> {
  return useQuery(optionsQuery);
}

export function isPlaceQueryLongEnough(query: string): boolean {
  return query.trim().length >= PLACE_QUERY_MIN_CHARS;
}

export function placeSuggestionsQuery(query: string, sessionId: string) {
  const trimmed = query.trim();
  return queryOptions({
    queryKey: [QUERY_KEYS.placeSuggestions, trimmed, sessionId],
    queryFn: ({ signal }) =>
      unwrap(apiClient.GET("/api/v1/places", { params: { query: { query: trimmed, session: sessionId } }, signal })),
    enabled: isPlaceQueryLongEnough(trimmed),
    staleTime: SERVER_DATA_STALE_TIME_MS,
    retry: false,
  });
}

export function usePlaceSuggestions(
  debouncedQuery: string,
  sessionId: string,
): Readonly<{ suggestions: readonly PlaceSuggestion[]; isFetching: boolean; error: ApiRequestError | null }> {
  const result = useQuery(placeSuggestionsQuery(debouncedQuery, sessionId));
  return {
    suggestions: result.data?.suggestions ?? NO_SUGGESTIONS,
    isFetching: result.isFetching,
    error: result.error,
  };
}

export function placeQuery(placeId: string) {
  return queryOptions({
    queryKey: [QUERY_KEYS.place, placeId],
    queryFn: ({ signal }) =>
      unwrap(apiClient.GET("/api/v1/places/{place_id}", { params: { path: { place_id: placeId } }, signal })),
    staleTime: SERVER_DATA_STALE_TIME_MS,
    retry: false,
  });
}

export function usePlace(placeId: string | null): UseQueryResult<Place, ApiRequestError> {
  return useQuery({
    ...placeQuery(placeId ?? ""),
    queryFn: placeId === null ? skipToken : placeQuery(placeId).queryFn,
  });
}

export function tripQuery(request: TripRequest | null) {
  return queryOptions({
    queryKey: [QUERY_KEYS.trip, request],
    queryFn:
      request === null
        ? skipToken
        : ({ signal }) => unwrap(apiClient.POST("/api/v1/trips", { body: request, signal })),
    staleTime: SERVER_DATA_STALE_TIME_MS,
    retry: false,
  });
}

export function useTripPlan(): UseQueryResult<Trip, ApiRequestError> {
  const request = useUiState((state) => state.tripRequest);
  return useQuery(tripQuery(request));
}

export function weatherGridRequestFor(trip: Trip, request: TripRequest): WeatherGridRequest {
  return {
    lines: trip.routes.map((route) => route.polyline),
    departure_utc: trip.departure_utc,
    load_weight: request.load_weight,
  };
}

export function weatherGridQuery(gridRequest: WeatherGridRequest | null) {
  return queryOptions({
    queryKey: [QUERY_KEYS.weatherGrid, gridRequest],
    queryFn:
      gridRequest === null
        ? skipToken
        : ({ signal }) => unwrap(apiClient.POST("/api/v1/weather-grid", { body: gridRequest, signal })),
    staleTime: SERVER_DATA_STALE_TIME_MS,
    retry: false,
  });
}

export function useWeatherGrid(): UseQueryResult<WeatherGrid, ApiRequestError> {
  const request = useUiState((state) => state.tripRequest);
  const trip = useTripPlan().data;
  const gridRequest = useMemo(
    () => (trip === undefined || request === null ? null : weatherGridRequestFor(trip, request)),
    [trip, request],
  );
  return useQuery(weatherGridQuery(gridRequest));
}
