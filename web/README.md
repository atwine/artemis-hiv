# ARTEMIS-HIV website (Phase 5)

Next.js + TypeScript + Tailwind + shadcn/ui (Radix underneath), with TanStack Query for data. It
talks to the FastAPI backend in `../backend` (see `../backend/README.md`); the browser calls the
backend directly, and the backend lets in only this site's address (`../ACCESS.md`).

The look is the owner's chosen design, Paper file "Artemis-HIV", page "FINAL · Day Rail with
floating tray". Its tokens (set "d7b") are the Tailwind theme in `src/app/globals.css`; the
shared frame (top bar, day rail, pane, floating tray, footer) is in `src/components/frame/`.
The screen wording (banners, alert headings, citations, disclaimer, finalize note) comes from
the API and is shown as sent.

## Run it

```
npm install
npm run dev            # http://127.0.0.1:3000 (or http://localhost:3000)
```

The backend must be running on 127.0.0.1:8000 (`python -m backend` from the repo root). A
different address goes in `NEXT_PUBLIC_ARTEMIS_API_URL`. It is not a secret: never put one in a
`NEXT_PUBLIC_` variable, since those reach every visitor's browser.

## Types from the backend

`src/lib/api/schema.d.ts` is generated from the backend's own OpenAPI schema, so the website and
the backend can't drift apart:

```
npm run api:types      # regenerate after a backend change
npm run api:check      # fails if the committed types no longer match the backend
```

Both run `scripts/export_openapi.py` with the repo's Python (`PYTHON` overrides which one).

## Tests

```
npm run test:unit      # small checks of plain functions (Node's own test runner)
npm run test:e2e       # the whole visit in a real browser
```

The browser tests drive the installed Chrome against the real backend and a throwaway Postgres
in Docker (`e2e/stack.ts`): their own ports (web 3100, API 8100, database 5435), a fresh
password each run, removed afterwards. No AI review runs, so nothing is spent. They need Docker
Desktop open and the search model on disk (`ARTEMIS_MODEL_DIR` in `../.env`). The first check of
a run loads the search model, so a run takes a minute or two.

`e2e/a11y.spec.ts` runs axe-core on every built screen against WCAG 2.2 AA and fails on any
problem it finds. One exception, the owner's choice: the tray's not-yet-reached step names keep the
design's grey (4.4:1), so only their contrast check is skipped. A clean run is a floor, not proof:
keyboard use and screen-reader wording still need a person. `ARTEMIS_A11Y_REPORT=<folder>` also
writes each screen's full axe result there.

`ARTEMIS_SCREENS=1 npx playwright test screens` saves 1366 x 768 screenshots to
`../docs/design/exports/phase5/` for checking against the Paper screens, including the AI-review
states the design doesn't draw (made from real rules-only replies; no model is called).
