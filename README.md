# Community Service Desk

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python: 3.14+](https://img.shields.io/badge/python-3.14%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17%2B-336791.svg)](https://www.postgresql.org/)

**Community Service Desk** is a lightweight, production-minded ticketing and service-desk application for community organizations, schools, associations, nonprofits, small businesses, and internal support teams.

Its immediate operational purpose is to provide a clean, accessible, and dependable system for receiving, triaging, assigning, communicating, and resolving support requests.

Its long-term architectural mission is equally vital:

> **Every resolved ticket should make the system better at helping resolve the next ticket.**

When support agents resolve an issue, structured resolution data—summary, root cause, verified remediation steps, and verification method—is captured and preserved. In v0.1, this institutional knowledge is indexed for deterministic search; in future versions, it will empower an authorization-bounded, advisory AI layer that suggests answers to incoming tickets while citing verified source resolutions.

---

## Community Software Registry (CSR) Submission Metadata

Prepared for Community Software Registry (CSR) "I Already Have Software" intake:

- **Software Name:** Community Service Desk
- **Package Name:** `community_service_desk`
- **Repository Slug:** `community-service-desk`
- **Version:** `0.1.1`
- **Description:** A lightweight service-desk application for community organizations to create, assign, track and resolve support tickets while preserving useful resolution knowledge for future support.
- **Intended Community:** Community organizations, schools, associations, nonprofits, small businesses and internal support teams.
- **License:** AGPL-3.0-only
- **Hosting / Cost Model:** 100% self-hostable open-source software. Requires zero paid cloud services (no AWS, Azure, GCP, or commercial AI API dependencies required).

---

## Features (v0.1 Scope)

- **Multi-Tenant Organization Workspaces:** Complete server-side isolation between organizations.
- **Role-Based Permissions:** Distinct access control for `organization_admin`, `agent`, and `requester`.
- **Full Ticket Lifecycle:** Deterministic state machine (`NEW`, `OPEN`, `IN_PROGRESS`, `WAITING_ON_REQUESTER`, `WAITING_INTERNAL`, `RESOLVED`, `CLOSED`) with reopening support.
- **Strict Internal Note Privacy:** Requesters **never** see internal notes in API responses or web templates. Notes are visually distinct with amber warning badges in the agent UI.
- **Structured Resolutions:** Dedicated resolution schema capturing summary, root cause, reproduction steps, verification method, and reusable knowledge markers.
- **Tenant-Scoped Search:** Filter and query across ticket numbers (`CSD-000001`), title, description, requester, status, priority, queue, category, tags, and date ranges.
- **AI-Ready Knowledge Retrieval Service:** Deterministic PostgreSQL/SQLite search abstraction returning ranked, bounded resolution evidence with source citations.
- **Safe Attachment Storage:** Private local disk storage abstraction with random UUID storage keys, file extension blocklists, and size enforcement.
- **Responsive & Accessible UI:** Server-rendered HTML (Jinja2) tested down to 390px and 320px mobile viewports, featuring semantic landmarks, skip links, and visible focus states.
- **Append-Only Event History:** Complete immutable audit log of status changes, assignments, notes, and resolutions.
- **Dual API & Web Interface:** Comprehensive FastAPI REST API (`/api/v1`) with interactive OpenAPI documentation alongside a full server-rendered web UI.

---

## Architecture Overview

```mermaid
graph TD
    Client["Browser / REST Client"] --> WebRouter["FastAPI Application"]
    WebRouter --> Auth["Authentication & Session Service (scrypt + JWT)"]
    WebRouter --> Authz["Authorization & Tenant Boundary Guard"]
    WebRouter --> TicketSvc["Ticket Lifecycle & Assignment Service"]
    WebRouter --> ConvSvc["Conversation Service (Internal Note Filter)"]
    WebRouter --> ResSvc["Structured Resolution Service"]
    WebRouter --> SearchSvc["Search Service (Tenant Scoped)"]
    WebRouter --> KnowledgeSvc["KnowledgeRetrievalService (AI-Ready Abstraction)"]
    WebRouter --> StorageSvc["Attachment Storage (Safe Local / Private Disk)"]

    TicketSvc --> DB[(PostgreSQL 17+ / SQLite)]
    ConvSvc --> DB
    ResSvc --> DB
    SearchSvc --> DB
    KnowledgeSvc --> DB
    StorageSvc --> Storage[(Private Disk Storage)]
```

For full architectural details, see [`docs/architecture.md`](docs/architecture.md).  
For the security policy and boundary enforcement, see [`docs/security.md`](docs/security.md).  
For lifecycle state transitions, see [`docs/ticket-lifecycle.md`](docs/ticket-lifecycle.md).  
For the 5-phase AI roadmap, see [`docs/ai-roadmap.md`](docs/ai-roadmap.md).

---

## Quick Start (Local Development)

### Prerequisites

- Python 3.11+ (Python 3.14 recommended and fully tested)
- Git
- Optional: PostgreSQL 17+ or Docker Compose

### 1. Clone & Setup Environment

```powershell
# Clone the repository
git clone https://github.com/community-service-desk/community-service-desk.git
cd community-service-desk

# Create virtual environment
python -m venv .venv

# Activate virtual environment (Windows PowerShell)
.\.venv\Scripts\Activate.ps1
# On Linux/macOS: source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"
```

### 2. Configure Environment

Copy the example environment configuration:

```powershell
cp .env.example .env
```

To run with zero external database dependencies (using local SQLite):
```env
CSD_DATABASE_URL=sqlite:///./csd_dev.db
```

Or connect to a local PostgreSQL 17 instance:
```env
CSD_DATABASE_URL=postgresql+psycopg://csd_user:csd_password@localhost:5432/csd_db
```

### 3. Run Migrations & Seed Demo Data

```powershell
# Apply Alembic database migrations
alembic upgrade head

# Seed synthetic demo organization and sample tickets
csd seed
```

### 4. Start the Application

```powershell
csd run --host 127.0.0.1 --port 8000
```

Open your browser to:
- **Web UI:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Interactive API Docs (Swagger):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **API Spec (ReDoc):** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Health Check:** [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)

---

## Running with Docker Compose

A production-aligned local development environment with PostgreSQL 17 is included:

```bash
docker compose up --build -d
```

- Web Application: `http://localhost:8000`
- PostgreSQL 17: `localhost:5433` (mapped from container 5432 to avoid host collisions)

---

## Synthetic Demo Identities

When the database is populated via `csd seed`, synthetic demo users are created:

| Identity | Role | Email | Purpose |
|---|---|---|---|
| **Sarah Admin** | `organization_admin` | `admin@metro-community.synthetic` | Manage members, queues, workspace |
| **Alex Support** | `agent` | `agent@metro-community.synthetic` | Queue triage, internal notes, resolve |
| **Jordan Requester** | `requester` | `requester@metro-community.synthetic` | Submit requests, view own tickets |

*Note: Organization slug is `metro-community`. Passwords for all demo accounts follow the pattern: `AdminPass123!`, `AgentPass123!`, `UserPass123!`.*

---

## Automated Test Suite

Community Service Desk includes a comprehensive automated test suite covering authentication, organization isolation, requester boundaries, internal note privacy, ticket lifecycle, history auditing, search, attachments, and accessibility.

```powershell
# Run the full test suite
pytest -v

# Run linting and formatting validation
ruff check .
ruff format --check .
```

---

## License

This project is licensed under the **GNU Affero General Public License v3.0** (`AGPL-3.0-only`).  
See the [`LICENSE`](LICENSE) file for the full text.
