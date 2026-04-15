# Atendoo

Bot de WhatsApp para clínicas de fisioterapia. Gestiona citas, clases grupales y derivaciones al fisio desde WhatsApp.

## Stack

FastAPI · PostgreSQL · Redis · OpenAI/Gemini · Google Calendar · Meta WhatsApp Cloud API

## Requisitos (dev)

- Python 3.12 (conda env `botllm`)
- Docker Desktop (PostgreSQL + Redis)
- Cuentas: Meta Developer, Google Cloud, OpenAI o Gemini

## Arrancar en local

```bash
conda activate botllm
cp .env.example .env   # rellenar variables
docker compose up -d   # solo db + redis
alembic upgrade head
python seed.py
uvicorn app.main:app --reload
```

Webhook local via ngrok:
```bash
ngrok http 8000
# Actualizar META_WEBHOOK_URL en Meta Developer Console
```

## Despliegue

Push a rama `deployment` → GitHub Actions despliega automáticamente en Hetzner.

Ver [DEPLOY.md](DEPLOY.md) para setup inicial y gestión del servidor.

## Estructura

```
app/
├── routers/    # FastAPI endpoints
├── services/   # Lógica de negocio
├── models/     # SQLAlchemy models
└── core/       # Config, DB, Redis, features
prompts/        # Prompts LLM en Markdown
static/         # Frontend panel admin
```