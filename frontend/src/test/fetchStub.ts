type FetchHandler = (request: Request) => Promise<Response>;

const unhandled: FetchHandler = (request) => Promise.reject(new Error(`Unexpected fetch ${request.url}`));

let currentHandler: FetchHandler = unhandled;

export function setFetchHandler(handler: FetchHandler): void {
  currentHandler = handler;
}

export function resetFetchHandler(): void {
  currentHandler = unhandled;
}

export function stubbedFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  return currentHandler(input instanceof Request ? input : new Request(input, init));
}

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}
