# 🤖 Security - ML & Scraping Engine

Microservicio de **IA y extracción de datos** del ecosistema Security, hecho con **Python y FastAPI**. Hace tres cosas:

- **Personas y casos en prensa**: vigilancia diaria de diarios nacionales (Google Noticias) y clasificación con un modelo local.
- **Indira**: agente IA (Ollama + `llama3.1:8b`) con tickets, memoria y feedback.
- **Scoring de riesgo** de personas.

Lo consume **solo** el backend Kotlin (repositorio Security-Backend), con la clave interna `X-Internal-Key`. Detalle del diseño: [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md).

- Puerto `8000` · Documentación interactiva: http://localhost:8000/docs · Salud: http://localhost:8000/api/v1/health
- Base de datos propia: **Postgres** (`security_ml`), con migraciones **Alembic** (se aplican solas al arrancar en Docker).

```text
app/
├── api/         # Endpoints REST (indira, personas, tickets, vigilancia)
├── agent/       # Agente Indira (LLM, herramientas, memoria)
├── core/        # Configuración, base de datos, seguridad
├── ml_engine/   # Detección de casos, matching y scoring
├── models/      # Tablas (SQLAlchemy)
├── scraper/     # Google Noticias / RSS
└── services/    # Casos, vigilancia y scheduler
```

---

## 🚀 Levantarlo (sin instalar Python ni Postgres)

**Necesitas únicamente:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) encendido y Git.

```bash
git clone https://github.com/jeliases-informaDev/Security-MachineLearning.git
cd Security-MachineLearning
docker compose up -d --build
```

La primera vez tarda ~1–2 minutos; después, segundos. Cuando `docker compose ps` muestre `ml` como **healthy**, abre http://localhost:8000/docs. Las tablas se crean solas.

| Quiero… | Comando |
|---|---|
| Ver logs | `docker compose logs -f ml` |
| Apagar (los datos se conservan) | `docker compose down` |
| Empezar de cero (borra la base local) | `docker compose down -v` |
| Aplicar cambios de código | `docker compose up -d --build ml` |

> Tu base de datos es **local y propia**: lo que hagas no afecta a nadie del equipo. La clave interna por defecto es la misma que usa Security-Backend, así que se conectan solos.

## 🗄️ Ver la base de datos y hacer consultas

Todo está explicado en **[docs/BASE-DE-DATOS.md](docs/BASE-DE-DATOS.md)** (qué base es, cómo conectarte con pgAdmin, mapa de tablas, cómo cargar los políticos) y las consultas listas para ejecutar están en **[docs/consultas.sql](docs/consultas.sql)**.

## 🧠 Indira (Ollama) — opcional

Indira necesita un modelo local: `llama3.1:8b` (4.9 GB de descarga y ~8 GB de RAM libres). **Sin Ollama todo lo demás funciona**; solo Indira responde "no disponible".

| Situación | Qué hacer |
|---|---|
| Ya tengo Ollama instalado en mi PC | Nada: el ML lo usa solo. Descarga el modelo una vez: `ollama pull llama3.1:8b` |
| No lo tengo y quiero Indira | `docker compose --profile ia up -d --build` (corre Ollama en Docker y descarga el modelo en segundo plano: `docker compose logs -f ollama-pull`) |
| Mi equipo no tiene RAM para el modelo | Pon `INDIRA_ENABLED=false` en `.env` y ejecuta `docker compose up -d` |

## 🛠️ Programar el ML (con recarga rápida)

Requisitos: **Python 3.12** y la base Postgres de Docker.

```bash
docker compose up -d postgres          # solo la base de datos

python -m venv venv
.\venv\Scripts\Activate.ps1            # Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env                 # Mac/Linux: cp
alembic upgrade head                   # crea las tablas (la primera vez y al traer migraciones nuevas)
python -m uvicorn main:app --reload
```

Si PowerShell bloquea el script del venv: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

Pruebas: `python -m unittest discover -s tests` (las pruebas y los scripts de vigilancia llegan con la rama `feature/vigilancia-prensa`)

## ⚙️ Configuración (todo opcional)

Los valores por defecto funcionan. Para cambiarlos copia `.env.example` como `.env` (no se sube a git).

| Variable | Para qué | Por defecto |
|---|---|---|
| `ML_PORT`, `POSTGRES_PORT` | Puertos en tu PC si están ocupados | `8000`, `5434` |
| `DATABASE_URL` | Postgres (al correr con uvicorn) | `…@localhost:5434/security_ml` |
| `INTERNAL_API_KEY` | Clave que debe mandar el backend (`X-Internal-Key`) | `dev-internal-key-change-me` |
| `ENTORNO` | `dev` abre `/indira-chat` y no exige clave si está vacía | `dev` |
| `INDIRA_ENABLED` | `false` apaga a Indira (responde 503) | `true` |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | Modelo de Indira (al correr con uvicorn) | `http://localhost:11434`, `llama3.1:8b` |
| `SCRAPING_AL_ARRANCAR` | Corre la vigilancia de prensa al encender (consume mucha CPU/RAM) | `false` |

## 🔧 Problemas comunes

| Síntoma | Solución |
|---|---|
| Puerto ocupado | Cambia `ML_PORT` o `POSTGRES_PORT` en `.env` y vuelve a `docker compose up -d`. |
| Indira responde error | Falta Ollama o el modelo: mira la sección de Indira. El resto del ML no se afecta. |
| `Cannot connect to the Docker daemon` | Abre Docker Desktop y espera a que diga *Engine running*. |
| 401 al probar en `/docs` | Las rutas piden el header `X-Internal-Key` (`dev-internal-key-change-me`). |

## 🤝 Flujo de trabajo del equipo (Git Flow)
Nunca trabajes directo en `main`: `git checkout -b feature/mi-tarea`, commits, `git push origin feature/mi-tarea` y abre un Pull Request.
