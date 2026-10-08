# Project rules

- Money is always an integer number of **cents** (`number`). Never compute with floating-point dollars;
  use the helpers in `src/money.ts` (`applyPercent`, `formatPrice`).
- Every handler reports errors with `sendError(res, status, code, message)` from `src/http.ts`; never write
  ad-hoc error JSON.
