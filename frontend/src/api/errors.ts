import { z } from "zod";
import { CLIENT_ERROR_CODES } from "@/keys";
import { apiText } from "@/text";

const fieldErrorSchema = z.object({
  field: z.string(),
  message: z.string(),
});

const errorEnvelopeSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    details: z.array(fieldErrorSchema).nullable(),
  }),
});

export type FieldError = Readonly<z.infer<typeof fieldErrorSchema>>;

export class ApiRequestError extends Error {
  override name = "ApiRequestError";
  readonly code: string;
  readonly status: number | null;
  readonly details: readonly FieldError[];

  constructor(code: string, message: string, status: number | null, details: readonly FieldError[]) {
    super(message);
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

export function parseErrorEnvelope(body: unknown, status: number | null): ApiRequestError {
  const result = errorEnvelopeSchema.safeParse(body);
  if (!result.success) {
    return new ApiRequestError(CLIENT_ERROR_CODES.unexpected, apiText.unexpectedError, status, []);
  }
  const { code, message, details } = result.data.error;
  return new ApiRequestError(code, message, status, details ?? []);
}

export function networkError(): ApiRequestError {
  return new ApiRequestError(CLIENT_ERROR_CODES.network, apiText.networkError, null, []);
}

export function fieldErrorsByField(error: ApiRequestError): ReadonlyMap<string, string> {
  return new Map(error.details.map((detail) => [detail.field, detail.message]));
}
