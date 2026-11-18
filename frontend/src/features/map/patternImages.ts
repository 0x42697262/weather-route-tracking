import {
  HATCH_PATTERN_SIZE_PX,
  HATCH_PATTERN_STRIPE_PX,
  HEX_CHANNEL_LENGTH,
  HEX_RADIX,
  OPAQUE_ALPHA,
  RGBA_CHANNELS,
} from "@/constants";
import { MAP_IMAGE_PREFIXES } from "@/keys";
import { MAP_COLORS, colorHex, colorKeysWithLineStyle, type ColorKey } from "@/theme/colors";

export type PatternImage = Readonly<{
  width: number;
  height: number;
  data: Uint8Array;
}>;

const HEX_PREFIX_LENGTH = 1;
const RGB_CHANNELS = 3;

export function hexToRgb(hex: string): readonly number[] {
  return Array.from({ length: RGB_CHANNELS }, (_, channel) => {
    const start = HEX_PREFIX_LENGTH + channel * HEX_CHANNEL_LENGTH;
    return Number.parseInt(hex.slice(start, start + HEX_CHANNEL_LENGTH), HEX_RADIX);
  });
}

export function hatchPatternImage(colorHexValue: string): PatternImage {
  const stripe = hexToRgb(colorHexValue);
  const gap = hexToRgb(MAP_COLORS.hatchStripe);
  const data = new Uint8Array(HATCH_PATTERN_SIZE_PX * HATCH_PATTERN_SIZE_PX * RGBA_CHANNELS);
  for (let row = 0; row < HATCH_PATTERN_SIZE_PX; row += 1) {
    for (let column = 0; column < HATCH_PATTERN_SIZE_PX; column += 1) {
      const onStripe = (row + column) % HATCH_PATTERN_SIZE_PX < HATCH_PATTERN_STRIPE_PX;
      const offset = (row * HATCH_PATTERN_SIZE_PX + column) * RGBA_CHANNELS;
      data.set([...(onStripe ? stripe : gap), OPAQUE_ALPHA], offset);
    }
  }
  return { width: HATCH_PATTERN_SIZE_PX, height: HATCH_PATTERN_SIZE_PX, data };
}

export function hatchImageId(key: ColorKey): string {
  return `${MAP_IMAGE_PREFIXES.hatch}${key}`;
}

export const PATTERN_IMAGES: ReadonlyMap<string, () => PatternImage> = new Map(
  colorKeysWithLineStyle("hatched").map((key) => [hatchImageId(key), () => hatchPatternImage(colorHex(key))]),
);
