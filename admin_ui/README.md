# edwmcp admin UI

A Flutter Web app that drives the admin REST API of the `edwmcp` MCP server. Use it to:

- View server health and the current MCP tool catalogue.
- Configure the badminton-database connection and the EDW connection (with a live "test" button against each).
- Edit the badminton schema mapping (table & column names) without hand-editing YAML.
- Tune the rotation rules (`balanced_skill` vs `queue_order`, rest period, players per game).
- Enable/disable the EDW skill and restrict it to specific schemas.

The admin UI is intentionally a separate process from the Badminton app's chatbot — this is the configuration plane, the chatbot is the data plane.

## Prerequisites

- Flutter SDK 3.19+ with web support enabled (`flutter config --enable-web`).

## Run the admin REST API

From the repo root:

```bash
EDWMCP_ADMIN_TOKEN=$(openssl rand -hex 16) \
EDWMCP_DEMO=1 \
edwmcp --admin
```

The admin API listens on `http://127.0.0.1:8766` by default. For loopback development you can drop the token requirement with `EDWMCP_ADMIN_INSECURE=1`, but the server refuses to start otherwise (fail-secure).

## Run the Flutter web app

```bash
cd admin_ui
flutter pub get
flutter run -d chrome
```

Sign in with the admin API URL (`http://127.0.0.1:8766`) and the bearer token you exported above. The token is cached in `localStorage` between sessions.

## Build for production

```bash
flutter build web --release
```

Drops static assets in `build/web`. Serve them behind nginx / Caddy / whatever, on the same origin as the admin API if you want to avoid configuring CORS.
