import { useQueryClient } from "@tanstack/react-query";
import { CircleAlert, LoaderCircle } from "lucide-react";
import { useState, type FormEvent } from "react";
import { placeQuery, tripQuery, useOptions, useTripPlan } from "@/api/queries";
import type { Options, Place } from "@/api/types";
import { ChoiceGroup } from "@/components/ChoiceGroup";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { LOAD_INPUT_STEP, NOW_REFRESH_MS } from "@/constants";
import { useNow } from "@/hooks/useNow";
import { usePreferences } from "@/features/preferences/context";
import {
  buildTripRequest,
  chosenRestStops,
  chosenSpacing,
  departureWindow,
  draftUsesCustomOptions,
  fieldErrorsFromDetails,
  spacingKey,
  type FieldErrors,
  type PickedPlace,
} from "@/features/trip-form/draft";
import { FieldMessage } from "@/features/trip-form/FieldMessage";
import { PlaceField } from "@/features/trip-form/PlaceField";
import { CustomOptionsNotice } from "@/features/trip-form/CustomOptionsNotice";
import { ELEMENT_IDS } from "@/keys";
import { formatZoneName, fromDateTimeInputValue, toDateTimeInputValue } from "@/lib/format";
import { displayUnit, formatDistanceKm, toDisplayValue, type UnitSystem } from "@/lib/units";
import { useUiActions, useUiState } from "@/state/context";
import { formText } from "@/text";

const NO_ERRORS: FieldErrors = {};

async function loadPlace(
  fetchPlace: (place: PickedPlace) => Promise<Place>,
  place: PickedPlace | null,
): Promise<Place | undefined> {
  if (place === null) {
    return undefined;
  }
  try {
    return await fetchPlace(place);
  } catch {
    return undefined;
  }
}

export function TripForm() {
  const options = useOptions();
  if (options.data === undefined) {
    return options.isError ? (
      <Alert variant="destructive">
        <CircleAlert aria-hidden="true" />
        <AlertDescription>{options.error.message}</AlertDescription>
      </Alert>
    ) : (
      <p className="text-sm text-muted-foreground">{formText.placeLoading}</p>
    );
  }
  return <TripFormFields options={options.data} />;
}

function loadBounds(options: Options, units: UnitSystem) {
  const load = options.options.load_weight;
  return {
    min: Math.floor(toDisplayValue(load.minimum, "mass", units)),
    max: Math.floor(toDisplayValue(load.maximum, "mass", units)),
  };
}

function TripFormFields({ options }: Readonly<{ options: Options }>) {
  const draft = useUiState((state) => state.draft);
  const { updateDraft, submitTrip } = useUiActions();
  const { units } = usePreferences();
  const queryClient = useQueryClient();
  const plan = useTripPlan();
  const tripRequest = useUiState((state) => state.tripRequest);
  const [clientErrors, setClientErrors] = useState<FieldErrors>(NO_ERRORS);

  const serverError = plan.error;
  const serverFieldErrors = serverError === null ? NO_ERRORS : fieldErrorsFromDetails(serverError.details);
  const errors: FieldErrors = { ...serverFieldErrors, ...clientErrors };
  const hasFieldErrors = Object.keys(serverFieldErrors).length > 0;

  const nowMs = useNow(NOW_REFRESH_MS);
  const nowIso = new Date(nowMs).toISOString();
  const departureRange = departureWindow(options, nowMs);
  const loadUnit = displayUnit("mass", units);
  const bounds = loadBounds(options, units);
  const spacingOption = options.options.checkpoint_spacing;
  const restOption = options.options.include_rest_stops;
  const spacingChoices = spacingOption.choices.map((choice) => ({
    value: spacingKey(choice),
    label: formatDistanceKm(choice.km, units),
  }));

  const fetchPlace = (place: PickedPlace) => queryClient.fetchQuery(placeQuery(place.id));

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const [origin, destination] = await Promise.all([
      loadPlace(fetchPlace, draft.origin),
      loadPlace(fetchPlace, draft.destination),
    ]);
    const departureUtc = draft.departureLocal === null ? null : fromDateTimeInputValue(draft.departureLocal);
    const result = buildTripRequest(
      draft,
      { origin, destination },
      options,
      units,
      new Date().toISOString(),
      departureUtc,
    );
    if (!result.ok) {
      setClientErrors(result.errors);
      return;
    }
    setClientErrors(NO_ERRORS);
    if (JSON.stringify(result.request) === JSON.stringify(tripRequest)) {
      await queryClient.refetchQueries({ queryKey: tripQuery(result.request).queryKey });
      return;
    }
    submitTrip(result.request);
  };

  const clearError = (field: keyof FieldErrors) =>
    setClientErrors((current) => (current[field] === undefined ? current : { ...current, [field]: undefined }));

  return (
    <form id={ELEMENT_IDS.tripForm} noValidate onSubmit={submit} className="flex flex-col gap-4" aria-busy={plan.isFetching}>
      <PlaceField
        id={ELEMENT_IDS.origin}
        label={formText.origin}
        value={draft.origin}
        onChange={(origin) => {
          updateDraft({ origin });
          clearError("origin");
        }}
        error={errors.origin}
      />
      <PlaceField
        id={ELEMENT_IDS.destination}
        label={formText.destination}
        value={draft.destination}
        onChange={(destination) => {
          updateDraft({ destination });
          clearError("destination");
        }}
        error={errors.destination}
      />
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={ELEMENT_IDS.departure}>{formText.departure}</Label>
        <Input
          id={ELEMENT_IDS.departure}
          type="datetime-local"
          className="h-11 text-base"
          value={draft.departureLocal ?? toDateTimeInputValue(nowIso)}
          min={toDateTimeInputValue(new Date(departureRange.earliestMs).toISOString())}
          max={toDateTimeInputValue(new Date(departureRange.latestMs).toISOString())}
          onChange={(event) => {
            updateDraft({ departureLocal: event.target.value });
            clearError("departure_utc");
          }}
          aria-invalid={errors.departure_utc === undefined ? undefined : true}
          aria-describedby={`${ELEMENT_IDS.departure}-message`}
        />
        <FieldMessage
          id={`${ELEMENT_IDS.departure}-message`}
          error={errors.departure_utc}
          hint={formText.departureHint(formatZoneName(nowIso))}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={ELEMENT_IDS.loadWeight}>{formText.loadWeight}</Label>
        <div className="flex items-center gap-2">
          <Input
            id={ELEMENT_IDS.loadWeight}
            type="number"
            inputMode="decimal"
            className="h-11 text-base"
            min={bounds.min}
            max={bounds.max}
            step={LOAD_INPUT_STEP}
            value={draft.loadValue}
            onChange={(event) => {
              updateDraft({ loadValue: event.target.value });
              clearError("load_weight");
            }}
            aria-invalid={errors.load_weight === undefined ? undefined : true}
            aria-describedby={`${ELEMENT_IDS.loadWeight}-message`}
          />
          <span className="w-8 shrink-0 text-sm text-muted-foreground">{loadUnit.label}</span>
        </div>
        <FieldMessage id={`${ELEMENT_IDS.loadWeight}-message`} error={errors.load_weight} />
      </div>
      {spacingOption.available ? (
        <div className="flex flex-col gap-1.5">
          <span id={ELEMENT_IDS.spacing} className="text-sm font-medium">
            {formText.spacing}
          </span>
          <ChoiceGroup
            label={formText.spacing}
            choices={spacingChoices}
            value={spacingKey(chosenSpacing(draft, options))}
            onChange={(key) => updateDraft({ spacingKey: key })}
          />
          <FieldMessage id={`${ELEMENT_IDS.spacing}-message`} error={errors.checkpoint_spacing} />
        </div>
      ) : null}
      <details className="group rounded-lg border px-3">
        <summary className="flex min-h-11 cursor-pointer items-center text-sm font-medium">{formText.advanced}</summary>
        <div className="flex flex-col gap-1 pb-3">
          <div className="flex min-h-11 items-center justify-between gap-3">
            <Label htmlFor={ELEMENT_IDS.restStops}>{formText.restStops}</Label>
            <Switch
              id={ELEMENT_IDS.restStops}
              checked={chosenRestStops(draft, options)}
              disabled={!restOption.available}
              onCheckedChange={(checked) => updateDraft({ includeRestStops: checked })}
            />
          </div>
          <FieldMessage
            id={`${ELEMENT_IDS.restStops}-message`}
            error={errors.include_rest_stops}
            hint={formText.restStopsHint}
          />
        </div>
      </details>
      {draftUsesCustomOptions(draft, options) ? (
        <CustomOptionsNotice onReset={() => updateDraft({ spacingKey: null, includeRestStops: null })} />
      ) : null}
      {serverError !== null && !hasFieldErrors ? (
        <Alert variant="destructive">
          <CircleAlert aria-hidden="true" />
          <AlertDescription>{serverError.message}</AlertDescription>
        </Alert>
      ) : null}
      <Button type="submit" size="lg" className="h-12 text-base" disabled={plan.isFetching}>
        {plan.isFetching ? (
          <>
            <LoaderCircle aria-hidden="true" className="size-5 animate-spin" />
            {formText.submitting}
          </>
        ) : (
          formText.submit
        )}
      </Button>
    </form>
  );
}
