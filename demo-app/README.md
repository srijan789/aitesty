# Demo App — Project Manager

A small full-stack demo: a React frontend (Vite) talking to an Express REST API, with 8
independently testable functionalities. One of the 8 has a real bug that is **only** exposed by
the automated test suite — running the app normally never shows it.

## Stack

- `backend/` — Express API on port 4000, in-memory data (resets on restart).
- `frontend/` — React 18 + Vite on port 5173, proxies `/api/*` to the backend.

## Setup

```bash
npm run install:all
```

(equivalent to `npm install` inside both `backend/` and `frontend/`)

## Run the app

```bash
npm run dev
```

Open http://localhost:5173. Create projects, add/toggle tasks, filter by status, edit, delete, and
search — everything works.

## Run the tests

```bash
npm test
```

This runs the backend's Jest + Supertest suite (`backend/tests/projects.test.js`), which has one
`describe` block per functionality. 16 of 17 tests pass; **one fails** in the update-project suite.

## The 8 functionalities

| # | Functionality | Endpoint |
|---|---|---|
| 1 | Create project | `POST /api/projects` |
| 2 | List projects (optional `?status=active\|completed`) | `GET /api/projects` |
| 3 | Get project details (tasks + progress) | `GET /api/projects/:id` |
| 4 | Update project | `PUT /api/projects/:id` |
| 5 | Delete project | `DELETE /api/projects/:id` |
| 6 | Add task to a project | `POST /api/projects/:id/tasks` |
| 7 | Toggle a task's complete state | `PATCH /api/projects/:id/tasks/:taskId/toggle` |
| 8 | Search projects by name | `GET /api/projects/search?q=` |

## The hidden bug (functionality 4 — update project)

`backend/src/store.js`'s `updateProject` checks `if (deadline)` (a truthy check) instead of
`if (deadline !== undefined)` before applying the new deadline. Pushing a deadline to a new date
always works — that's a truthy value — but sending `deadline: null` to **clear** an existing
deadline is silently ignored: the request returns `200 OK`, yet the old deadline is still there.

- App: editing a project to set a later deadline always works, which is the only thing a normal
  demo walkthrough does — nobody thinks to test "remove the deadline I just set."
- Tests: `backend/tests/projects.test.js`, suite `4. Update project`, has a test that creates a
  project with a deadline, clears it via `PUT { deadline: null }`, and asserts the response's
  `deadline` is `null`. It fails with `Expected: null, Received: "2026-01-01"` — a plain, obvious
  wrong-value bug (no crash, no special characters, no HTTP error code) caught only by the test
  suite.
