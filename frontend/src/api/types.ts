import type { components } from "@/api/schema";

type Schemas = components["schemas"];

export type Options = Schemas["OptionsOut"];
export type RiskLevelRow = Schemas["RiskLevelOut"];
export type RiskLevel = Schemas["RiskLevel"];
export type SpacingChoice = Schemas["SpacingOut"];
export type HeatmapLayerRow = Schemas["HeatmapLayerOut"];
export type Attribution = Schemas["AttributionOut"];
export type ApiUnit = Schemas["Unit"];
export type WeatherVariable = Schemas["WeatherVariable"];
export type WeatherVariableRow = Schemas["WeatherVariableOut"];
export type TripOptionName = Schemas["TripOptionName"];

export type PlaceSuggestion = Schemas["PlaceSuggestionOut"];
export type Place = Schemas["PlaceOut"];

export type TripRequest = Schemas["TripIn"];
export type TripEnd = Schemas["TripEndIn"];
export type Trip = Schemas["TripOut"];
export type Route = Schemas["RouteOut"];
export type RouteSource = Schemas["RouteSource"];
export type RouteSummary = Schemas["RouteSummaryOut"];
export type RouteWarning = Schemas["RouteWarning"];
export type TripWarning = Schemas["TripWarning"];
export type NoRecommendationReason = Schemas["NoRecommendationReason"];
export type Checkpoint = Schemas["CheckpointOut"];
export type Stretch = Schemas["StretchOut"];
export type StretchKind = Schemas["StretchKind"];
export type Stop = Schemas["StopOut"];
export type StopKind = Schemas["StopKind"];
export type TruckPosition = Schemas["TruckPositionOut"];

export type WeatherGridRequest = Schemas["WeatherGridIn"];
export type WeatherGrid = Schemas["WeatherGridOut"];
export type GridLayer = Schemas["GridLayerOut"];
