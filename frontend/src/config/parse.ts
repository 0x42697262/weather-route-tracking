import { z } from "zod";
import { configText } from "@/text";

export const DEFAULT_API_BASE_URL = "/api";
export const DEFAULT_MAP_STYLE_URL = "https://tiles.openfreemap.org/styles/liberty";

const publicEnvSchema = z.object({
  VITE_API_BASE_URL: z.string().min(1).default(DEFAULT_API_BASE_URL),
  VITE_MAP_STYLE_URL: z.url().default(DEFAULT_MAP_STYLE_URL),
});

export type PublicConfig = Readonly<{
  apiBaseUrl: string;
  mapStyleUrl: string;
}>;

export class InvalidPublicConfigError extends Error {
  override name = "InvalidPublicConfigError";
}

export function parsePublicConfig(env: Readonly<Record<string, unknown>>): PublicConfig {
  const result = publicEnvSchema.safeParse(env);
  if (!result.success) {
    const problems = result.error.issues.map((issue) =>
      configText.invalidVariable(issue.path.join("."), issue.message),
    );
    throw new InvalidPublicConfigError(problems.join("; "));
  }
  return Object.freeze({
    apiBaseUrl: result.data.VITE_API_BASE_URL,
    mapStyleUrl: result.data.VITE_MAP_STYLE_URL,
  });
}
