import { Combobox as ComboboxPrimitive } from "@base-ui/react";
import { useState } from "react";
import { isPlaceQueryLongEnough, usePlaceSuggestions } from "@/api/queries";
import type { PlaceSuggestion } from "@/api/types";
import {
  ComboboxContent,
  ComboboxEmpty,
  ComboboxInput,
  ComboboxItem,
  ComboboxList,
} from "@/components/ui/combobox";
import { Label } from "@/components/ui/label";
import { PLACE_QUERY_MIN_CHARS, PLACE_SEARCH_DEBOUNCE_MS } from "@/constants";
import { FieldMessage } from "@/features/trip-form/FieldMessage";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { formText } from "@/text";

type PlaceFieldProps = Readonly<{
  id: string;
  label: string;
  value: PlaceSuggestion | null;
  onChange: (place: PlaceSuggestion | null) => void;
  error: string | undefined;
}>;

const INPUT_CHANGE_REASON = "input-change";

function newSessionId(): string {
  return crypto.randomUUID();
}

export function PlaceField({ id, label, value, onChange, error }: PlaceFieldProps) {
  const [sessionId, setSessionId] = useState(newSessionId);
  const [query, setQuery] = useState(value?.title ?? "");
  const [open, setOpen] = useState(false);
  const debouncedQuery = useDebouncedValue(query, PLACE_SEARCH_DEBOUNCE_MS);
  const searching = value === null || query !== value.title;
  const { suggestions, isFetching } = usePlaceSuggestions(searching ? debouncedQuery : "", sessionId);
  const messageId = `${id}-message`;
  const hint = isPlaceQueryLongEnough(query) ? undefined : formText.placeHint(PLACE_QUERY_MIN_CHARS);

  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <ComboboxPrimitive.Root<PlaceSuggestion>
        items={suggestions}
        filter={null}
        open={open && searching && isPlaceQueryLongEnough(query)}
        onOpenChange={setOpen}
        value={value}
        inputValue={query}
        onInputValueChange={(next, details) => {
          setQuery(next);
          if (details.reason !== INPUT_CHANGE_REASON) {
            return;
          }
          setOpen(true);
          if (value !== null && next !== value.title) {
            onChange(null);
          }
        }}
        onValueChange={(picked) => {
          onChange(picked);
          if (picked !== null) {
            setQuery(picked.title);
            setSessionId(newSessionId());
            setOpen(false);
          }
        }}
        itemToStringLabel={(item) => item.title}
        isItemEqualToValue={(item, selected) => item.id === selected.id}
      >
        <ComboboxInput
          id={id}
          placeholder={formText.placePlaceholder}
          showTrigger={false}
          autoComplete="off"
          aria-invalid={error === undefined ? undefined : true}
          aria-describedby={messageId}
          className="h-11 w-full text-base"
        />
        <ComboboxContent>
          <ComboboxEmpty>{isFetching || debouncedQuery !== query ? formText.placeSearching : formText.placeNoResults}</ComboboxEmpty>
          <ComboboxList>
            {(item: PlaceSuggestion) => (
              <ComboboxItem key={item.id} value={item} className="min-h-11 flex-col items-start gap-0 py-1.5">
                <span className="font-medium">{item.title}</span>
                <span className="text-xs text-muted-foreground">{item.subtitle}</span>
              </ComboboxItem>
            )}
          </ComboboxList>
        </ComboboxContent>
      </ComboboxPrimitive.Root>
      <FieldMessage id={messageId} error={error} hint={value === null ? hint : value.subtitle} />
    </div>
  );
}
