# Personal Finance Web

Production dashboard for the thesis demo. The app is built with Next.js 16,
React 19, TypeScript, Tailwind v4, TanStack Query and Recharts.

## Role in the project

- Main UI for the production demo at `http://localhost:3000`.
- Talks only to its local route handler at `/api/proxy/*`.
- The proxy performs HTTP calls to FastAPI and injects BasicAuth credentials from
  server-side env vars (`API_USERNAME`, `API_PASSWORD`) when configured.

## Development

```bash
npm install
npm run dev
```

Optional `.env.local`:

```ini
API_URL=http://localhost:8000
API_USERNAME=admin
API_PASSWORD=change-me
```

## Quality checks

```bash
npx tsc --noEmit
npx eslint src
npm run build
```
