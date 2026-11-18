import createClient from "openapi-fetch";
import type { paths } from "@/api/schema";
import { networkError, parseErrorEnvelope } from "@/api/errors";
import { config } from "@/config";

export function apiOrigin(apiBaseUrl: string, pageOrigin: string): string {
  return new URL(apiBaseUrl, pageOrigin).origin;
}

export const apiClient = createClient<paths>({
  baseUrl: apiOrigin(config.apiBaseUrl, window.location.origin),
});

type FetchResult<Data> = Readonly<{
  data?: Data;
  error?: unknown;
  response: Response;
}>;

export async function unwrap<Data>(request: Promise<FetchResult<Data>>): Promise<Data> {
  let result: FetchResult<Data>;
  try {
    result = await request;
  } catch {
    throw networkError();
  }
  if (result.response.ok && result.data !== undefined) {
    return result.data;
  }
  throw parseErrorEnvelope(result.error, result.response.status);
}
