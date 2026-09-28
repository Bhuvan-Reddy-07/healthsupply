# HealthSupply: Healthcare Supply Chain Intelligence & Redistribution System

An offline-tolerant, tamper-evident, federated healthcare supply chain intelligence platform designed for resource-constrained health systems (PHCs, CHCs, and District Hospitals).

## Architecture Overview

```
                      +-----------------------------+
                      |   Central Health Authority  |
                      |   Control Center Dashboard  |
                      +--------------+--------------+
                                     |
                         HTTPS / REST / WebSocket
                                     |
                      +--------------v--------------+
                      |  FastAPI Modular Monolith   |
                      |  /backend (Python 3.11)     |
                      +---+----------+----------+---+
                          |          |          |
         +----------------+          |          +----------------+
         |                           |                           |
+--------v--------+         +--------v--------+         +--------v--------+
| TimescaleDB/PG  |         |   NATS Message  |         | Flower Node &   |
| 10 Schema Tables|         |  Broker Stream  |         | FL Aggregator   |
+-----------------+         +-----------------+         +-----------------+
         ^                           ^
         |                           |
  Offline Sync / SMS          Offline Sync / SMS
         |                           |
+--------+--------+         +--------+--------+
| Country A Node  |         | Country B Node  |
| Facility PWA    |         | Facility PWA    |
+-----------------+         +-----------------+
```

### Monorepo Structure
- `/edge`: Facility Progressive Web App (Offline-First with IndexedDB/Dexie, Automerge CRDT, and GS1 barcode scanner).
- `/backend`: FastAPI modular monolith (`/api/v1`, Pydantic v2 schemas, JWT auth stub, structured JSON logging, Alembic migrations, SQLAlchemy ORM).
- `/ml`: Demand forecasting (LightGBM quantile regression P10/P50/P90, Croston SBA baselines, censored demand imputation, MinT hierarchical reconciliation, and CUSUM outbreak detection).
- `/dashboard`: Operations dashboard (React + MapLibre GL live heat maps, alert feeds, and human-in-the-loop transfer proposal workflows).
- `/simulator`: Synthetic data generator (200 facilities across 2 non-IID countries, 150 items catalog, 24-month daily consumption with weekly clinic cycles, monsoon/summer seasonality, monthly batch replenishment, stockout censoring traps, and logistic outbreak injector).
- `/infra`: Docker Compose configuration with PostgreSQL 15 + TimescaleDB extension, NATS JetStream, and append-only database triggers.
- `/tests`: Complete verification suite.

---

## Phase 0 Acceptance Criteria Verification

| Criteria | Implementation Detail | Status |
| :--- | :--- | :---: |
| **One-Command Dataset Generation** | `python -m simulator.cli --generate` or `make simulate` generates 200 facilities across 2 countries, 150 categorized items, batches, and transactions. | **VERIFIED** |
| **Exact ERD Conformance** | All 10 tables implemented: `facilities`, `items`, `stock_batches`, `stock_transactions`, `bed_states`, `staff_attendance`, `forecasts`, `alerts`, `transfer_proposals`, `audit_log`. | **VERIFIED** |
| **Batch-Level Granularity** | `stock_batches` enforces `current_quantity`, `mfg_date`, `expiry_date`, and `gs1_gtin` with non-negative check constraints. | **VERIFIED** |
| **Tamper-Evident Audit Log** | Cryptographic SHA-256 hash chaining + ORM & database trigger append-only guards strictly blocking UPDATE and DELETE. | **VERIFIED** |
| **Stock-Out Censoring & Negative Stock Guard** | Unit tests prove batch stock goes negative nowhere (`min(qty) >= 0`) and `censored=True` is tagged with `unfulfilled_quantity > 0` during stockouts. | **VERIFIED** |

---

## Quickstart Instructions

### Prerequisites
- Python 3.11+
- Docker & Docker Compose (optional for containerized deployment)

### 1. Environment Setup
```bash
cp .env.example .env
pip install -r backend/requirements.txt
```

### 2. Run Database Migrations
```bash
alembic upgrade head
```

### 3. Generate Simulated 2-Country Dataset
Generate 200 facilities (100 in Country A, 100 in Country B), 150 items, and 24 months of daily simulation history:
```bash
python -m simulator.cli --generate --facilities 200 --items 150 --months 24
```

### 4. Inject an Outbreak
Simulate an epidemic surge in a district:
```bash
python -m simulator.cli --inject-outbreak-only --outbreak-district Kolar --outbreak-class antimalarial --outbreak-multiplier 4.0 --outbreak-ramp 7
```

### 5. Run Verification Test Suite
```bash
pytest tests/ -v
```

### 6. Start the Modular Monolith
```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```
Interactive OpenAPI documentation will be accessible at: `http://localhost:8000/docs`

### 7. Containerized Deployment (Docker Compose)
```bash
docker compose up -d postgres nats backend
```
