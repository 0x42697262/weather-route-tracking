import type { Position } from "geojson";
import {
  DECIMAL_BASE,
  POLYLINE_ASCII_OFFSET,
  POLYLINE_CHUNK_BITS,
  POLYLINE_CHUNK_MASK,
  POLYLINE_CONTINUATION_BIT,
  POLYLINE_PRECISION,
} from "@/constants";

const BINARY_BASE = 2;
const COORDINATE_FACTOR = DECIMAL_BASE ** POLYLINE_PRECISION;

type Cursor = { index: number };

function readSignedValue(encoded: string, cursor: Cursor): number {
  let result = 0;
  let shift = 0;
  let chunk: number;
  do {
    chunk = encoded.charCodeAt(cursor.index) - POLYLINE_ASCII_OFFSET;
    cursor.index += 1;
    result += (chunk & POLYLINE_CHUNK_MASK) * BINARY_BASE ** shift;
    shift += POLYLINE_CHUNK_BITS;
  } while (chunk >= POLYLINE_CONTINUATION_BIT && cursor.index < encoded.length);
  return result % BINARY_BASE === 1 ? -(result + 1) / BINARY_BASE : result / BINARY_BASE;
}

export function decodePolyline(encoded: string): Position[] {
  const positions: Position[] = [];
  const cursor: Cursor = { index: 0 };
  let latitudeE5 = 0;
  let longitudeE5 = 0;
  while (cursor.index < encoded.length) {
    latitudeE5 += readSignedValue(encoded, cursor);
    longitudeE5 += readSignedValue(encoded, cursor);
    positions.push([longitudeE5 / COORDINATE_FACTOR, latitudeE5 / COORDINATE_FACTOR]);
  }
  return positions;
}
