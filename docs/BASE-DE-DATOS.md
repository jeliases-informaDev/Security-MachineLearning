# Base de datos del ML (`security_ml`, PostgreSQL)

Esta guía responde: **¿qué base es, dónde está, cómo la veo y qué hay en cada tabla?**
Las consultas listas para ejecutar están en [consultas.sql](consultas.sql).

Aquí viven las **personas públicas de la política** que se vigilan en la prensa, sus **casos** (acusaciones, denuncias, investigaciones, sentencias, absoluciones) con el enlace a la noticia original, y todo lo de **Indira** (conversaciones) y los **tickets**.

> Las listas negativas / PEP del backend (`security_db`, MySQL) son otra base distinta. Ver `docs/BASE-DE-DATOS.md` del repositorio **Security-Backend**.

---

## 1. ¿Cuál es y dónde está?

La base se llama **`security_ml`** (PostgreSQL). Dónde está depende de a qué apunte `DATABASE_URL`:

| Cómo lo levantas | Dónde está la base | Qué contiene |
|---|---|---|
| `docker compose up -d` en este repo | Contenedor `postgres` → `localhost:5434`, usuario `postgres`, clave `postgres` | Base **nueva y propia**: las tablas vacías (las crea Alembic al arrancar). Hay que cargar los políticos (sección 4). |
| `.env` con otro `DATABASE_URL` | Donde diga esa URL (un Postgres instalado en tu PC, uno compartido, etc.) | Lo que haya ahí. Si es un Postgres instalado en tu PC **no lo verás en Docker**: ábrelo con tu cliente apuntando a ese host y puerto. |

Para saber a cuál apunta **tu** ML, mira `DATABASE_URL` en tu `.env` (host, puerto y base; la clave no hace falta mostrarla).

## 2. Cómo ver las tablas y su contenido

| Herramienta | Cómo conectarte |
|---|---|
| **pgAdmin 4** (se instala con PostgreSQL en Windows) | *Servers → Register → Server*: Host `localhost` · Puerto `5434` (compose) · Base `security_ml` · Usuario `postgres` · Clave `postgres`. Luego clic derecho en la base → **Query Tool** y pega una consulta. |
| **DBeaver / IntelliJ (Database)** | Nueva conexión PostgreSQL con esos mismos datos. |
| **Terminal** | `docker compose exec postgres psql -U postgres -d security_ml` y luego `\dt` (tablas) o `\d personas` (columnas). |

Luego abre [consultas.sql](consultas.sql) y ejecuta una consulta a la vez.

## 3. Mapa de tablas

```
 fuentes (diarios) ──► articulos_raw (noticias guardadas) ──► casos ◄── personas
                                                              (hallazgo)   (políticos vigilados)

 conversaciones_indira ──► mensajes_indira ──► ejemplos_verificados
          └──► reportes_generados

 tickets ──► mensajes_ticket
```

### Personas y casos en prensa

| Tabla | Qué guarda |
|---|---|
| `personas` | Figuras públicas vigiladas: `nombres`, `apellidos`, `nombres_alternativos`, `es_pep`, `cargo_pep`, `nivel_riesgo_score`, `origen`, `estado_verificacion`, y `external_id` (id en el backend Kotlin, si existe). |
| `casos` | Un hallazgo: `persona_id`, `tipo`, `categoria_delito`, `resumen`, **`url_fuente`** (enlace directo a la noticia), `score_confianza`, `estado_revision`. |
| `articulos_raw` | La noticia tal cual se guardó (`titulo`, `contenido_texto`, `url`, `fecha_publicacion`). Permite reprocesar sin volver a la web del diario. |
| `fuentes` | Los diarios (`nombre`, `dominio`, `activo`). |

Valores que verás (se guardan en **MAYÚSCULAS**):

| Columna | Valores |
|---|---|
| `casos.tipo` | `ACUSACION`, `DENUNCIA`, `INVESTIGACION`, `SENTENCIA`, `ABSOLUCION` |
| `casos.estado_revision` | `PENDIENTE`, `VERIFICADO`, `DESCARTADO` |
| `personas.origen` | `KOTLIN_SYNC`, `SCRAPER_DETECTADO` |
| `personas.estado_verificacion` | `PENDIENTE`, `VERIFICADO`, `DESCARTADO` |

**Garantías del diseño:** nada se publica solo (todo caso nace `PENDIENTE` y requiere revisión humana); cada caso apunta a su noticia original; los homónimos son el riesgo principal (por eso existe `estado_verificacion`).

**Nombres:** se guardan como salen en la prensa (unos con tilde, otros sin: `Cerrón`, `Lopez Aliaga`). Busca con `ILIKE '%cerr%'`, no con igualdad exacta.

### Indira (agente IA) y tickets

| Tabla | Qué guarda |
|---|---|
| `conversaciones_indira` / `mensajes_indira` | Historial del chat (`rol`: user / assistant / tool; `feedback`: positivo / negativo). |
| `ejemplos_verificados` | Pares pregunta–respuesta que recibieron feedback **positivo** (si luego se marca negativo, se borra). Sirven para mejorar a Indira. |
| `reportes_generados` | Reportes que Indira generó (PDF, XLSX o JSON). |
| `tickets` / `mensajes_ticket` | Tickets de soporte (propios del ecosistema) y su hilo de mensajes. |

`alembic_version` es de control interno de las migraciones: no la toques.

## 4. Cómo tener datos para consultar

Una base nueva del compose está **vacía**. Para cargar políticos y casos (el servicio debe estar levantado):

```bash
# 1) Carga las figuras políticas a vigilar (solo nombres; es seguro repetirlo, no duplica)
docker compose exec ml python -m scripts.seed_vigilancia_politica

# 2) Busca sus casos en la prensa (tarda varios minutos; necesita Internet y Ollama con el modelo)
docker compose exec ml python -m scripts.ejecutar_vigilancia --persona Boluarte --dias 60 --max 10
```

- El paso 1 deja ~29 personas (la mayoría PEP). Con eso ya puedes consultar `personas`.
- El paso 2 crea los `casos` (todos `PENDIENTE`). Sin Ollama no se generan casos. Quita `--persona` para recorrer a todos.
- Una vez al día (6:00, hora de Lima) la vigilancia corre sola **si el servicio está encendido**. Con `SCRAPING_AL_ARRANCAR=true` también corre al encender si la última corrida fue hace más de 20 h (en el compose viene apagado).
- Alternativa de demostración: `scripts/seed_demo_personas.py` guarda noticias reales de varios diarios y crea figuras con casos solo donde la propia noticia reporta uno.

**Consultar sin Docker ni base:** el ML expone `GET /api/v1/personas/buscar?q=Boluarte` (http://localhost:8000/docs). Pide el header `X-Internal-Key` (por defecto `dev-internal-key-change-me`). Desde la web solo llega por el chat de **Indira** (su herramienta `consultar_persona` lee estas tablas); el backend lo expone como `GET /api/ml/personas/buscar?q=…` (con JWT), pero ninguna pantalla lo usa todavía.
