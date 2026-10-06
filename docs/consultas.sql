-- =====================================================================================
-- Consultas utiles sobre la base security_ml (PostgreSQL). Todas son de SOLO LECTURA.
-- Abre este archivo en pgAdmin 4 (Query Tool) / DBeaver / IntelliJ (Database) y ejecuta una a la vez.
-- Explicacion de cada tabla y como se relacionan: docs/BASE-DE-DATOS.md
--
-- Nota: los nombres se guardan tal como salen en la prensa (unos con tilde, otros sin, p. ej. "Cerrón"
-- y "Lopez Aliaga"). Por eso se busca con ILIKE y un trozo del apellido: '%cerr%', '%lopez%'.
-- =====================================================================================


-- 1) ¿Que tablas hay y cuantas filas tienen?
SELECT relname AS tabla, n_live_tup AS filas
FROM pg_stat_user_tables
WHERE relname <> 'alembic_version'
ORDER BY n_live_tup DESC, relname;


-- 2) Todas las personas publicas vigiladas (politicos), de mayor a menor riesgo
SELECT nombres, apellidos, es_pep, cargo_pep, nivel_riesgo_score, estado_verificacion, origen, creado_en
FROM personas
ORDER BY nivel_riesgo_score DESC, apellidos;


-- 3) ¿Cuantos casos tiene cada persona?
SELECT p.nombres, p.apellidos, p.es_pep,
       COUNT(c.id)                                              AS casos,
       COUNT(c.id) FILTER (WHERE c.estado_revision = 'VERIFICADO') AS verificados,
       COUNT(c.id) FILTER (WHERE c.estado_revision = 'PENDIENTE')  AS pendientes
FROM personas p
LEFT JOIN casos c ON c.persona_id = p.id
GROUP BY p.id, p.nombres, p.apellidos, p.es_pep
ORDER BY casos DESC, p.apellidos;


-- 4) Los casos de UNA persona con el enlace a la noticia. Cambia el apellido donde dice "cambia aqui".
SELECT p.nombres, p.apellidos, c.tipo, c.categoria_delito, c.resumen,
       c.score_confianza, c.estado_revision, c.url_fuente, c.creado_en
FROM personas p
JOIN casos c ON c.persona_id = p.id
WHERE p.apellidos ILIKE '%boluarte%'              -- <== cambia aqui
ORDER BY c.creado_en DESC;


-- 5) Casos por tipo y estado de revision
SELECT tipo, estado_revision, COUNT(*) AS casos
FROM casos
GROUP BY tipo, estado_revision
ORDER BY casos DESC;


-- 6) Casos que faltan revisar (los mas recientes primero). Nada se publica solo: todo empieza "PENDIENTE".
SELECT c.creado_en, p.nombres, p.apellidos, c.tipo, c.categoria_delito, LEFT(c.resumen, 110) AS resumen, c.url_fuente
FROM casos c
JOIN personas p ON p.id = c.persona_id
WHERE c.estado_revision = 'PENDIENTE'
ORDER BY c.creado_en DESC
LIMIT 50;


-- 7) Caso -> noticia original -> diario (trazabilidad completa)
SELECT p.apellidos, c.tipo, f.nombre AS diario, a.titulo, a.fecha_publicacion, a.url
FROM casos c
JOIN personas p        ON p.id = c.persona_id
JOIN articulos_raw a   ON a.id = c.articulo_id
JOIN fuentes f         ON f.id = a.fuente_id
ORDER BY a.fecha_publicacion DESC NULLS LAST
LIMIT 50;


-- 8) Noticias guardadas por diario
SELECT f.nombre AS diario, f.dominio, f.activo,
       COUNT(a.id)                                   AS noticias,
       COUNT(a.id) FILTER (WHERE a.procesado)        AS procesadas,
       MAX(a.fecha_scrapeo)                          AS ultimo_scrapeo
FROM fuentes f
LEFT JOIN articulos_raw a ON a.fuente_id = f.id
GROUP BY f.id, f.nombre, f.dominio, f.activo
ORDER BY noticias DESC;


-- 9) Conversaciones con Indira (el agente IA): cuantos mensajes tiene cada una
SELECT cv.id, cv.canal, cv.estado, cv.creado_en, COUNT(m.id) AS mensajes
FROM conversaciones_indira cv
LEFT JOIN mensajes_indira m ON m.conversacion_id = cv.id
GROUP BY cv.id, cv.canal, cv.estado, cv.creado_en
ORDER BY cv.creado_en DESC;


-- 10) Ultimas preguntas y respuestas de Indira
SELECT m.creado_en, m.rol, LEFT(m.contenido, 140) AS contenido, m.feedback
FROM mensajes_indira m
ORDER BY m.creado_en DESC
LIMIT 30;


-- 11) Tickets de soporte con la cantidad de mensajes de cada uno
SELECT t.creado_en, t.tipo, t.asunto, t.estado, t.prioridad, t.creado_por, COUNT(mt.id) AS mensajes
FROM tickets t
LEFT JOIN mensajes_ticket mt ON mt.ticket_id = t.id
GROUP BY t.id, t.creado_en, t.tipo, t.asunto, t.estado, t.prioridad, t.creado_por
ORDER BY t.creado_en DESC;
