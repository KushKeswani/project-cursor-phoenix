# Range Breakout Strategy Logic — Overview

Morning range breakout across four instruments. Each defines a range, then trades breakouts during a later window with SL, PT, and optional breakeven/trail.

---

**CL** — Builds range in the first 30 minutes of RTH. Trades breakouts in a midday window. Fixed risk, breakeven, trailing stop.

**MGC** — Same morning range concept. Volatility-adaptive exits. One trade per day, narrow trade window.

**MNQ** — Range built after cash open. Midday breakout window. Fixed SL/PT, no breakeven or trail.

**YM** — Morning range, midday trade window. Fixed risk with breakeven and trailing stop.
