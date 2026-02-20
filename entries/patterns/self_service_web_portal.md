---
title: "Building a Self-Service Research Portal"
type: pattern
tags: [web-portal, full-stack, dashboard, self-service, monitoring, flask, react, api]
domain: software-engineering
created: 2026-02-20
updated: 2026-02-20
confidence: medium
complexity: medium
related: []
---

# Building a Self-Service Research Portal

## Problem
Research testbeds and lab infrastructure need a web-based portal where team members can monitor equipment status, trigger experiments, view results, and manage configurations — without needing SSH access or direct API knowledge. The portal needs to be functional quickly (PhD timelines), maintainable by a small team, and flexible enough to integrate with heterogeneous backend systems.

## Context
Built for the Seascan project and applicable to similar research infrastructure portals (Open Ireland testbed management, experiment dashboards). The key constraint: a single developer (PhD student) needs to build and maintain it, so architectural simplicity trumps enterprise patterns.

## Approach
1. **Backend API**: Python (Flask or FastAPI) serving a REST API. Connects to equipment, databases, and processing pipelines. Handles auth, session management, and data aggregation.
2. **Frontend**: React or simple HTML/JS dashboard depending on complexity needs. For monitoring-heavy use cases, a dashboard framework (Grafana-like) may be faster than custom UI.
3. **Data layer**: PostgreSQL for structured data, file system for large artifacts (spectra, logs). Time-series data may warrant InfluxDB or TimescaleDB.
4. **Deployment**: Docker Compose for bundling frontend, backend, database. Deploy on lab server or VM. Nginx reverse proxy for HTTPS.

## Key Decisions
- **Flask/FastAPI over Django**: For a portal with <20 views and API-first design, a microframework is faster to develop and easier to reason about. Django's ORM and admin are overkill for most research portals.
- **REST over GraphQL**: REST is simpler, team already knows it, and the query patterns are predictable (not ad-hoc graph traversals). GraphQL overhead not justified.
- **Docker Compose over Kubernetes**: Single-server deployment. K8s is massive overhead for a research portal with <10 concurrent users. Docker Compose gives reproducible deployment with minimal complexity.
- **Auth strategy**: For internal/lab use, basic auth or institutional SSO (if available) is sufficient. Don't over-engineer auth for a <20 user portal. Use Flask-Login or FastAPI middleware with JWT.

## Pitfalls & Gotchas
- **Scope creep is the #1 killer**: Start with the smallest useful portal (status dashboard + one key workflow). Resist adding features until the core is stable and actually used.
- **Equipment API reliability**: Lab equipment APIs (NETCONF, REST, SNMP) are often flaky. Build retry logic and graceful degradation from day one. Show "last known state" with timestamps rather than erroring out.
- **Long-running tasks**: Experiments and data processing can take minutes to hours. Never block the HTTP request. Use background task queues (Celery, or simpler: threading + status polling endpoint).
- **State management**: Avoid storing critical state only in the frontend. The backend should be the source of truth. Use the database, not session variables, for experiment state.
- **CORS and reverse proxy pain**: When frontend and backend are on different ports/origins during development, CORS issues waste hours. Configure CORS correctly from the start, and match the production reverse proxy setup in dev.
- **Don't build a custom charting library**: Use Plotly, Chart.js, or embed Grafana panels. Custom charting is a time sink that never ends.

## Recipe
To build a research portal from scratch:

1. **Define the 3 most important pages**: Typically: (a) status/monitoring dashboard, (b) experiment trigger/control, (c) results viewer. Start with only these.
2. **Backend skeleton**:
   - FastAPI/Flask app with route stubs for each page's data needs
   - Equipment connector module (abstracted behind an interface so you can mock it)
   - SQLAlchemy models for persistent data (experiments, configurations, users)
   - Background task runner for long operations
3. **Frontend skeleton**:
   - React with a component library (MUI, Ant Design) for rapid UI development
   - OR server-rendered templates (Jinja2) if the portal is mostly read-only dashboards
   - A single layout with sidebar navigation
4. **Connect real data**: Replace mocks with actual equipment API calls. Test with real hardware early — simulated APIs hide real-world issues.
5. **Deployment**:
   - Dockerfile for backend, Dockerfile for frontend (or serve static build from backend)
   - docker-compose.yml with backend, frontend, postgres, nginx
   - Basic HTTPS with self-signed cert or Let's Encrypt
6. **Iterate**: Ship the minimal version. Get users on it. Prioritize what they actually ask for, not what you think they need.

## Verification
- Portal loads and shows current equipment status within 5 seconds
- Users can trigger a key workflow end-to-end through the UI
- Portal gracefully handles equipment being offline (shows stale data, not errors)
- Works across team members' machines (not just your laptop)
- Deployment can be reproduced from scratch with `docker-compose up`
