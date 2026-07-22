# Personal Finance Web

Web dashboard for Personal Finance App. It is built with Next.js 16, React 19,
TypeScript, Tailwind v4, TanStack Query and Recharts. Project setup and the
Docker workflow are documented in the [root README](../../README.md).

## Role in the project

- Main UI at `http://localhost:3000`.
- Talks only to its local route handler at `/api/proxy/*`.
- The proxy forwards cookies and `Set-Cookie`, disables API response caching
  and injects BasicAuth credentials from server-side environment variables
  (`API_USERNAME`, `API_PASSWORD`) when configured.

## Development

Requires Node.js 24.

```bash
npm ci
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
npm run typecheck
npm run lint
npm run build
```
