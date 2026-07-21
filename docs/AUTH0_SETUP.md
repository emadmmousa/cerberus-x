# Auth0 setup (Firebreak)

Firebreak uses the **official Auth0 Python SDK** (`auth0-server-python`) for
Regular Web App login — not a hand-rolled OAuth flow.

## 1. Auth0 Dashboard (required)

Application type: **Regular Web Application**

Under **Settings**, set:

| Field | Value |
|-------|--------|
| Allowed Callback URLs | `http://localhost:5000/callback` |
| Allowed Logout URLs | `http://localhost:5000` |
| Allowed Web Origins | `http://localhost:5000` |
| Token Endpoint Authentication | `Post` (client_secret_post) |

Save changes.

## 2. Local `.env` (never commit secrets)

Add (paste **Client Secret** from Auth0 yourself — do not commit it):

```bash
AUTH0_DOMAIN=firebreaker.us.auth0.com
AUTH0_CLIENT_ID=<from Auth0>
AUTH0_CLIENT_SECRET=<from Auth0>
AUTH0_SECRET=<run: openssl rand -hex 32>
APP_BASE_URL=http://localhost:5000
```

## 3. Restart orchestrator

```bash
docker compose restart orchestrator
# or rebuild if deps are missing in the image:
# docker compose build orchestrator && docker compose up -d orchestrator
```

Ensure the orchestrator image/venv has `auth0-server-python` (see `requirements.txt`).

## 4. Try it

1. Open Mission Control → Options → Auth strip  
2. **Sign in** / **Signup** → Auth0 Universal Login  
3. After callback you should land on `/` authenticated  
4. **Logout** clears Auth0 + Flask session  

Routes: `/auth/sso` (start SSO), `/callback`, `/logout` (SDK). SPA Login page is `/login`.
Status: `/auth/status`, `/api/oidc/status` (`login_path` → `/auth/sso`).
