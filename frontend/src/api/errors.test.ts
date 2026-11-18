import { describe, expect, it } from "vitest";
import { apiOrigin, unwrap } from "@/api/client";
import { ApiRequestError, fieldErrorsByField, parseErrorEnvelope } from "@/api/errors";

describe("parseErrorEnvelope", () => {
  it("reads code, message and field details", () => {
    const error = parseErrorEnvelope(
      {
        error: {
          code: "invalid_input",
          message: "Check the highlighted fields.",
          details: [{ field: "load_kg", message: "Must be at least 0." }],
        },
      },
      422,
    );
    expect(error.code).toBe("invalid_input");
    expect(error.message).toBe("Check the highlighted fields.");
    expect(error.status).toBe(422);
    expect(fieldErrorsByField(error).get("load_kg")).toBe("Must be at least 0.");
  });

  it("accepts null details", () => {
    const error = parseErrorEnvelope({ error: { code: "upstream", message: "Down.", details: null } }, 503);
    expect(error.details).toEqual([]);
  });

  it("falls back to an unexpected error for any other body", () => {
    const error = parseErrorEnvelope("<html>Bad gateway</html>", 502);
    expect(error.code).toBe("unexpected_response");
    expect(error.status).toBe(502);
  });
});

describe("unwrap", () => {
  it("returns the data of a successful response", async () => {
    const response = new Response(null, { status: 200 });
    await expect(unwrap(Promise.resolve({ data: { status: "ok" }, response }))).resolves.toEqual({
      status: "ok",
    });
  });

  it("throws the parsed envelope of a failed response", async () => {
    const response = new Response(null, { status: 404 });
    const body = { error: { code: "not_found", message: "No such place.", details: null } };
    await expect(unwrap(Promise.resolve({ error: body, response }))).rejects.toMatchObject({
      code: "not_found",
      status: 404,
    });
  });

  it("throws a network error when the request fails", async () => {
    const failed = unwrap(Promise.reject(new TypeError("Failed to fetch")));
    await expect(failed).rejects.toBeInstanceOf(ApiRequestError);
    await expect(failed).rejects.toMatchObject({ code: "network_error", status: null });
  });
});

describe("apiOrigin", () => {
  it("resolves a relative base URL against the page", () => {
    expect(apiOrigin("/api", "https://app.example.com")).toBe("https://app.example.com");
  });

  it("keeps an absolute base URL's origin", () => {
    expect(apiOrigin("https://api.example.com/api", "https://app.example.com")).toBe(
      "https://api.example.com",
    );
  });
});
