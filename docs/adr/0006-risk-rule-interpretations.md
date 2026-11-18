# 0006. Risk rule interpretations

Status: accepted, 2026-11-16

## Context

The risk tables leave four things open: which level an edge value belongs to, how No Travel
affects the ranking, how checkpoint levels become distances, and how the average risk is computed.

## Decision

- **Edges:** a value on a band edge belongs to the higher level. The exceptions are the No Travel
  bounds of rain (1.00 in/h) and snow (3.0 in/h), which are exclusive because the source says
  "over". Wind bands are continuous.
- **No Travel in the ranking:** No Travel distance is the first ranking key, before Severe. Such a
  route stays visible with a warning. If every route has No Travel distance, there is no
  recommendation.
- **Stretches:** a stretch between two neighboring checkpoints takes the worse level of its ends.
  Where the two ends differ, extra samples between them locate the change (`risk-model.md`,
  method `refine`), once that step is built.
- **Average risk:** levels scored 0 to 4, weighted by distance in km.
- **Unknown weather:** a stretch with no forecast has no level. Its distance is reported and warned
  about, stays out of the ranking key, and is left out of the average.
- **Wind:** the wind condition is sustained wind speed, not gusts.

## Consequences

- `risk-model.md` and the band edge tests state these exactly.
- Taking the worse end is cautious: a route's risky distance can be overstated by up to one
  spacing per change of level. A smaller spacing reduces that.
- These are defaults of behavior, not rule set data; changing them is a code change with an ADR.
