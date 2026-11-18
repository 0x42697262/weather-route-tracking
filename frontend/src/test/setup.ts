import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";
import { resetFetchHandler, stubbedFetch } from "@/test/fetchStub";

globalThis.fetch = stubbedFetch;

afterEach(() => {
  cleanup();
  resetFetchHandler();
});
