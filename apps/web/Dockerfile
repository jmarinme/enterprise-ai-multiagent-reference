FROM node:20-alpine

WORKDIR /app

ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL

# Microsoft Entra ID authentication build-time config (PBI-11-01/PBI-11-01A) — Vite inlines
# VITE_* at build time, not container runtime, so these must be real build ARGs, matching the
# VITE_API_URL pattern above. Defaults match the confirmed DEV App Registration (none of these
# are secrets); VITE_ENTRA_REDIRECT_URI/VITE_ENTRA_POST_LOGOUT_REDIRECT_URI have no safe
# universal default (they must match this deployment's own origin) so they default empty,
# which apps/web/src/config/env.ts falls back from to window.location.origin(/auth-bridge.html)
# at runtime. PBI-11-01B: redirectUri MUST be the dedicated bridge page
# (auth-bridge.html/src/auth-bridge.ts), not the SPA root — see that module's own docstring.
ARG VITE_ENTRA_AUTHORITY=https://login.microsoftonline.com/common
ARG VITE_ENTRA_CLIENT_ID=67d95215-5a31-416a-99ab-5fe203fb7c32
ARG VITE_ENTRA_API_SCOPE=api://67d95215-5a31-416a-99ab-5fe203fb7c32/access_as_user
ARG VITE_ENTRA_REDIRECT_URI=
ARG VITE_ENTRA_POST_LOGOUT_REDIRECT_URI=
ENV VITE_ENTRA_AUTHORITY=$VITE_ENTRA_AUTHORITY
ENV VITE_ENTRA_CLIENT_ID=$VITE_ENTRA_CLIENT_ID
ENV VITE_ENTRA_API_SCOPE=$VITE_ENTRA_API_SCOPE
ENV VITE_ENTRA_REDIRECT_URI=$VITE_ENTRA_REDIRECT_URI
ENV VITE_ENTRA_POST_LOGOUT_REDIRECT_URI=$VITE_ENTRA_POST_LOGOUT_REDIRECT_URI

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

EXPOSE 3000

CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "3000"]
