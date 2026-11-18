import type { Route } from "@/api/types";
import { DISPLAY_LOCALE, ROUTE_LETTER_CODE_START } from "@/constants";
import { routeText } from "@/text";

const NUMERIC_COLLATOR = new Intl.Collator(DISPLAY_LOCALE, { numeric: true });

export function routeNames(routes: readonly Pick<Route, "id">[]): ReadonlyMap<string, string> {
  const ids = routes.map((route) => route.id).sort(NUMERIC_COLLATOR.compare);
  return new Map(
    ids.map((id, index) => [id, routeText.name(String.fromCharCode(ROUTE_LETTER_CODE_START + index))]),
  );
}

export function routeName(names: ReadonlyMap<string, string>, routeId: string): string {
  return names.get(routeId) ?? routeId;
}
