# Arquitectura — Security ML & Scraping Engine

Este documento define el modelo de datos y el flujo de interacción entre módulos para las dos capacidades nuevas del microservicio:

1. **Extracción de casos/delitos/acusaciones** desde diarios peruanos, vinculados al perfil de la persona.
2. **Agente IA "Indira"**: consultas sobre la plataforma/datos, generación de reportes y gestión de tickets.

Decisiones tomadas (2026-09-18):

| Decisión | Resuelto como |
|---|---|
| Persistencia | Este microservicio tiene **BD propia** (Postgres). Kotlin consume esta API cuando necesita datos frescos. |
| Motor IA de Indira | **Modelo propio, autohospedado** (costo $0, sin pagar por token, sin depender de ningún proveedor externo). Recomendado: **Ollama** corriendo **Llama 3.1 8B** o **Qwen2.5 7B-Instruct** (buen soporte de español, corre en CPU aunque va más rápido con GPU) sobre infraestructura del propio equipo. Control total: el modelo, el servidor y los datos son 100% internos — nada sale a un tercero. Fase posterior (opcional): fine-tuning con datos propios (casos, tickets, FAQs) para especializarlo más al dominio, cuando haya GPU disponible para entrenar. |
| Tickets | Sistema **propio**, modelado en este ecosistema. |

> Nota: `main.py` ya registra el servicio como **"ComplyTools - ML & Scraping API"** — se asume que "Security" y "ComplyTools" son el mismo producto; confirmar si hay que unificar el nombre.

---

## 1. Modelo de datos

### 1.1 `Persona`
Entidad central. Puede originarse en Kotlin (KYC/onboarding) o ser creada aquí cuando el scraper detecta a alguien no registrado (candidato pendiente de verificación).

| Campo | Tipo | Notas |
|---|---|---|
| `id` | UUID | PK |
| `external_id` | UUID, nullable | ID de la Persona en el backend Kotlin, si existe (permite sincronizar) |
| `tipo_documento` | enum (DNI, RUC, CE, PASAPORTE) | |
| `numero_documento` | string, nullable | Puede no conocerse aún si solo viene de una noticia |
| `nombres`, `apellidos` | string | |
| `nombres_alternativos` | string[] | Alias, apodos, variantes de escritura encontradas en prensa |
| `fecha_nacimiento` | date, nullable | |
| `es_pep` | bool | |
| `cargo_pep` | string, nullable | |
| `nivel_riesgo_score` | float | Salida del `ml_engine` (scoring) |
| `origen` | enum (kotlin_sync, scraper_detectado) | |
| `estado_verificacion` | enum (pendiente, verificado, descartado) | Relevante cuando `origen = scraper_detectado` |
| `creado_en`, `actualizado_en` | timestamp | |

### 1.2 `Fuente` (diario)
| Campo | Tipo | Notas |
|---|---|---|
| `id` | UUID | PK |
| `nombre` | string | Ej. "El Comercio", "La República" |
| `dominio` | string | |
| `activo` | bool | |
| `config_scraper` | JSON | Selectores CSS/XPath, paginación, etc. |
| `frecuencia_minutos` | int | Cada cuánto se re-scrapea |

### 1.3 `ArticuloRaw`
Resultado crudo del scraping, antes de procesar con ML. Permite reprocesar sin volver a golpear la web del diario.

| Campo | Tipo | Notas |
|---|---|---|
| `id` | UUID | PK |
| `fuente_id` | FK → Fuente | |
| `url` | string, unique | Para dedupe |
| `hash_contenido` | string | Dedupe adicional si la URL cambia pero el contenido no |
| `titulo`, `contenido_texto` | text | |
| `fecha_publicacion` | date, nullable | |
| `fecha_scrapeo` | timestamp | |
| `procesado` | bool | Si ya pasó por el `ml_engine` |

### 1.4 `Caso`
El hallazgo final: un delito/acusación vinculado a una persona, con su fuente.

| Campo | Tipo | Notas |
|---|---|---|
| `id` | UUID | PK |
| `persona_id` | FK → Persona | |
| `articulo_id` | FK → ArticuloRaw | Trazabilidad a la fuente original |
| `tipo` | enum (acusacion, denuncia, investigacion, sentencia, absolucion) | |
| `categoria_delito` | string | Ej. "lavado de activos", "corrupción", "narcotráfico" — taxonomía a definir |
| `resumen` | text | Generado/extraído del artículo |
| `url_fuente` | string | Link directo a la noticia (lo que pide el negocio) |
| `score_confianza` | float | Confianza del ML de que el artículo realmente refiere a esta Persona (evita falsos positivos por homónimos) |
| `estado_revision` | enum (pendiente, verificado, descartado) | Revisión humana antes de mostrarse como definitivo |
| `creado_en` | timestamp | |

### 1.5 `Ticket`
| Campo | Tipo | Notas |
|---|---|---|
| `id` | UUID | PK |
| `usuario_id` | UUID | Referencia al usuario en Kotlin (external ref, no FK real) |
| `canal` | enum (chat_indira, web, app) | |
| `tipo` | enum (consulta, reporte, soporte, reclamo) | |
| `asunto` | string | |
| `estado` | enum (abierto, en_proceso, resuelto, cerrado) | |
| `prioridad` | enum (baja, media, alta) | |
| `creado_por` | enum (usuario, indira) | Indira puede auto-crear tickets al detectar un problema en la conversación |
| `creado_en`, `actualizado_en` | timestamp | |

### 1.6 `MensajeTicket`
Hilo de mensajes de un ticket (usuario ↔ Indira ↔ agente humano).

| Campo | Tipo | Notas |
|---|---|---|
| `id` | UUID | PK |
| `ticket_id` | FK → Ticket | |
| `autor` | enum (usuario, indira, agente_humano) | |
| `contenido` | text | |
| `creado_en` | timestamp | |

### 1.7 `ConversacionIndira` / `MensajeIndira`
Historial de chat, separado de `Ticket` (una conversación puede o no derivar en un ticket).

| Campo | Tipo | Notas |
|---|---|---|
| `id` | UUID | PK (Conversacion) |
| `usuario_id` | UUID | |
| `canal` | enum (web, app) | |
| `estado` | enum (activa, cerrada) | |
| — | — | `MensajeIndira`: `id`, `conversacion_id`, `rol` (user/assistant/tool), `contenido`, `tool_calls` (JSON), `tokens_usados` (control de costo del modelo económico), `creado_en` |

### 1.8 `ReporteGenerado`
| Campo | Tipo | Notas |
|---|---|---|
| `id` | UUID | PK |
| `solicitado_por` | UUID (usuario) o `conversacion_id` | |
| `tipo_reporte` | string | Ej. "resumen de riesgo de persona", "casos nuevos del mes" |
| `formato` | enum (pdf, xlsx, json) | |
| `parametros` | JSON | |
| `url_archivo` | string | |
| `creado_en` | timestamp | |

---

## 2. Flujo de módulos

```
┌─────────────┐   scheduler (APScheduler)
│  Fuente(s)  │──────────────┐
└─────────────┘              ▼
                    ┌───────────────────┐
                    │  app/scraper/     │  BeautifulSoup + requests
                    │  (por diario)     │  → guarda ArticuloRaw (dedupe por url/hash)
                    └─────────┬─────────┘
                              ▼
                    ┌───────────────────┐
                    │  app/ml_engine/   │  NER (extrae nombres + DNI si aparece)
                    │  preprocessing +  │  Clasificación (tipo/categoría de delito)
                    │  models           │  Matching contra Persona (fuzzy match)
                    └─────────┬─────────┘
                              ▼
                    ┌───────────────────┐
                    │  app/services/    │  Orquesta: crea/actualiza Persona
                    │  (casos_service)  │  candidata + Caso + score_confianza
                    └─────────┬─────────┘
                              ▼
                    ┌───────────────────┐
                    │  app/api/         │  Expuesto a Kotlin:
                    │                   │  GET /personas/{id}/casos
                    │                   │  POST /personas/{id}/scoring
                    └───────────────────┘

┌──────────────────────────────────────────────────────────┐
│  app/agent/indira/  (módulo nuevo, independiente)         │
│                                                            │
│  Usuario (web/app) → POST /api/v1/indira/chat              │
│      → Claude Haiku 4.5 (Anthropic SDK) + tool-use:        │
│           - consultar_persona_casos(persona_id)            │
│           - generar_reporte(tipo, parametros)               │
│           - crear_ticket(asunto, descripcion)                │
│           - buscar_en_docs_plataforma(query)  [RAG sobre    │
│             FAQ/documentación de la página/app]             │
│      → guarda en ConversacionIndira / MensajeIndira          │
└──────────────────────────────────────────────────────────┘
```

**Puntos clave:**
- El scraper NUNCA escribe directo en `Persona`/`Caso`; pasa siempre por `ml_engine` (matching/scoring) y `services` (reglas de negocio: cuándo crear vs. actualizar, umbral de confianza para auto-publicar vs. requerir revisión humana).
- `Caso` siempre queda trazable a su `ArticuloRaw` y por ende a la URL original — cumple el requisito de "adjuntar link al perfil".
- Indira es un módulo aparte (`app/agent/indira/`, no dentro de `ml_engine`) porque su ciclo de vida (prompts, tools, modelo LLM) es distinto al de los modelos de scoring/NER. Comparte la misma BD para leer `Persona`/`Caso` y escribir `Ticket`/`Conversacion`.
- Los "falsos positivos por homónimo" son el riesgo principal del scraper (ej. dos personas con el mismo nombre). Por eso `estado_verificacion` en `Persona` y `estado_revision` en `Caso` existen — nada se muestra como "caso confirmado" sin pasar un umbral de confianza o revisión humana.

---

## 3. Dependencias nuevas a agregar

```
sqlalchemy
alembic
psycopg2-binary          # o asyncpg si se va a async
pydantic-settings
ollama                    # cliente Python para hablar con el modelo local vía Ollama
apscheduler               # scheduling del scraper
rapidfuzz                 # fuzzy matching de nombres (Persona)
spacy (o similar)         # NER para extracción de entidades en ml_engine
```

Pendiente decidir: motor de vector store para el RAG de Indira (pgvector sobre el mismo Postgres es lo más simple dado que ya usamos Postgres — evita sumar otra pieza de infraestructura).

**Requisitos de servidor para el modelo local:** Llama 3.1 8B / Qwen2.5 7B cuantizado (Q4) necesita ~6-8 GB de RAM libres para correr en CPU (más lento, aceptable para uso interno de bajo volumen) o una GPU con ≥8 GB VRAM para respuestas más rápidas. Confirmar qué tiene disponible el servidor donde se va a desplegar este microservicio antes de fijar el modelo exacto.

---

## 4. Pendientes / decisiones abiertas

- [ ] Confirmar specs del servidor de despliegue (RAM/GPU disponible) para elegir el tamaño exacto del modelo local.
- [ ] Taxonomía cerrada de `categoria_delito` (¿la define compliance o se infiere libremente del ML?).
- [ ] Lista inicial de diarios (`Fuente`) a scrapear.
- [ ] Umbral de `score_confianza` para auto-publicar un `Caso` vs. requerir revisión humana.
- [ ] Confirmar nombre del producto: README dice "Security", `main.py` dice "ComplyTools".
