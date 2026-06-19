# Schedula Frontend

React + Vite frontend for Schedula.

This app provides role-based UI flows for lecturers and secretaries, including login, constraint submission/management, schedule views, secretary setup screens, and breaking-constraints dashboards.

## Stack

- React 19
- React Router 7
- Vite 7
- ESLint 9

## Main Routes

Defined in `src/App.jsx`:

- `/` -> redirects to `/login`
- `/login`
- `/lecturer/home`
- `/lecturer/constraints` -> redirects to `/lecturer/constraints/write`
- `/lecturer/constraints/write`
- `/lecturer/constraints/manage`
- `/lecturer/schedule`
- `/secretary/home`
- `/secretary/semester-setup`
- `/secretary/schedule-manager`
- `/secretary/schedule-manager/overview`
- `/secretary/schedule-manager/assignments`
- `/secretary/breaking-constraints`
- `/secretary/constraints`
- `/secretary/fairness`

## Environment Variables

Copy `.env.example` to `.env` and adjust as needed. The shipped `.env.example` only documents the first three variables; the optional ones below need to be added manually if you want to override their defaults.

- `VITE_API_BASE_URL` (default expected locally: `http://localhost:8000`)
- `VITE_API_PREFIX_LECTURER` (default: `/lecturer`)
- `VITE_API_PREFIX_SECRETARY` (default: `/secretary`)
- Optional: `VITE_API_PREFIX_AUTH` (defaults in code to `/auth`). Currently used only for logout; the login request always hits a hard-coded `${VITE_API_BASE_URL}/auth/login` path.
- Optional: `VITE_WS_BASE_URL` (otherwise derived from `VITE_API_BASE_URL`).

## Run Locally

```powershell
npm install
npm run dev
```

Vite dev server runs on:

- `http://localhost:5173`

## Build, Preview, and Lint

```powershell
npm run build
npm run preview
npm run lint
```

## Docker

The Dockerfile starts the Vite dev server inside the container on port `5173`.

Build and run manually:

```powershell
docker build -t schedula-frontend .
docker run --rm -p 5173:5173 --env VITE_API_BASE_URL=http://localhost:8000 schedula-frontend
```

Or run via the deployment stack in the sibling repo (`SchedulaDeployment`).

## Developer Notes

- Mock mode is available from the login flow and persisted in localStorage (`schedula_mock_mode`). When the key is absent, mock mode is on by default (see `src/contexts/MockModeContext.jsx`).
- Constraint parsing progress can be tracked in real time via WebSocket (`/ws/constraints/{session_id}`); the URL is derived from `VITE_WS_BASE_URL` or `VITE_API_BASE_URL` in `src/hooks/useConstraintProgress.js`.
- Telegram linking UX is rendered as a card on the lecturer home dashboard (`/lecturer/home`), not as a separate notifications page. The card calls backend routes under `/lecturer/notifications/telegram-link/*`.

## Notable UI

A few areas worth knowing about when navigating the codebase:

- Login intro animation (`IntroAnimation.jsx`) and the mock/real toggle on `LoginPage.jsx`.
- Lecturer home cards (`LecturerHome1.jsx`): `SystemStatusCard`, `LecturerConstraintsActions`, `MyCoursesCard`, `TelegramLinkingCard`, plus a CTA into `/lecturer/schedule` once a schedule is published.
- Constraint authoring (`/lecturer/constraints/write`): live progress via `useConstraintProgress` and `StageProgressIndicator`, edit flow via `EditConstraintForm`.
- Schedule visualization and editing: `WeeklyScheduleGrid`, `EditableWeeklyScheduleGrid`, `DaySelector`, `TimeSlotEditor`, `LecturersListDrawer`, `EditIndicatorBadge`.
- Shared chrome: `HeaderBar`, `Sidebar` / `SecretarySidebar`, `StatusToast`, `ConfirmModal`, `DataTable`, `NoScheduleState`, copy in `tooltipTexts.js`.
