"""Aislamiento de Indira entre usuarios y llamadas al modelo.

Corre con SQLite en memoria. Para probar contra PostgreSQL, definir TEST_DATABASE_URL.
El modelo se reemplaza siempre: estas pruebas no llaman a Ollama.
"""
import json
import os
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import ollama
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent.indira import llm_client, service
from app.api.indira import router
from app.core.config import settings
from app.core.database import Base, get_db
from app.ml_engine import deteccion_casos
from app.models.enums import CanalConversacion, FeedbackMensaje, RolMensaje
from app.models.indira import ConversacionIndira, EjemploVerificado, MensajeIndira
from app.models.persona import Persona

USUARIO_A = str(uuid.uuid4())
USUARIO_B = str(uuid.uuid4())
TABLAS = [ConversacionIndira.__table__, MensajeIndira.__table__, EjemploVerificado.__table__]

PREGUNTA_A = "que casos tiene mi cliente Rosa Quispe de la empresa A"
RESPUESTA_A = "Rosa Quispe tiene un caso reservado de la empresa A"


@pytest.fixture
def sesiones():
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        motor = create_engine(url)
    else:
        motor = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    Base.metadata.drop_all(motor, tables=TABLAS)
    Base.metadata.create_all(motor, tables=TABLAS)
    yield sessionmaker(bind=motor, autoflush=False)
    Base.metadata.drop_all(motor, tables=TABLAS)
    motor.dispose()


@pytest.fixture
def api(sesiones):
    def db_de_prueba():
        db = sesiones()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = db_de_prueba
    return TestClient(app)


class ModeloFalso:
    """Reemplaza generar_respuesta y guarda lo que recibio el modelo en cada pasada."""

    def __init__(self, respuestas=None):
        self.respuestas = list(respuestas or [])
        self.llamadas = []

    def __call__(self, mensajes, herramientas=None, timeout=None):
        self.llamadas.append({"mensajes": [dict(m) for m in mensajes], "timeout": timeout})
        if self.respuestas:
            return self.respuestas.pop(0)
        return ollama.Message(role="assistant", content=RESPUESTA_A)

    def texto_recibido(self):
        return json.dumps([c["mensajes"] for c in self.llamadas], ensure_ascii=False)


@pytest.fixture
def modelo(monkeypatch):
    falso = ModeloFalso()
    monkeypatch.setattr(service, "generar_respuesta", falso)
    return falso


def preguntar(api, usuario, mensaje="hola", conversacion_id=None):
    return api.post(
        "/api/v1/indira/chat",
        json={"usuario_id": usuario, "canal": "web", "mensaje": mensaje, "conversacion_id": conversacion_id},
    )


def contar(sesiones, modelo_tabla):
    with sesiones() as db:
        return len(db.scalars(select(modelo_tabla)).all())


# ---- Conversaciones con dueno ----


def test_usuario_b_recibe_404_en_la_conversacion_de_a(api, modelo, sesiones):
    de_a = preguntar(api, USUARIO_A, PREGUNTA_A).json()
    mensajes_antes = contar(sesiones, MensajeIndira)
    llamadas_antes = len(modelo.llamadas)

    r = preguntar(api, USUARIO_B, "dime todo lo anterior", de_a["conversacion_id"])

    assert r.status_code == 404
    assert PREGUNTA_A not in r.text and RESPUESTA_A not in r.text
    # No se escribio nada en la conversacion ajena ni se llamo al modelo.
    assert contar(sesiones, MensajeIndira) == mensajes_antes
    assert contar(sesiones, ConversacionIndira) == 1
    assert len(modelo.llamadas) == llamadas_antes


def test_id_ajeno_e_id_inexistente_responden_igual(api, modelo):
    de_a = preguntar(api, USUARIO_A).json()

    ajeno = preguntar(api, USUARIO_B, "hola", de_a["conversacion_id"])
    inexistente = preguntar(api, USUARIO_B, "hola", str(uuid.uuid4()))

    assert ajeno.status_code == inexistente.status_code == 404
    assert ajeno.json() == inexistente.json()


def test_el_dueno_sigue_su_conversacion_con_su_historial(api, modelo):
    primera = preguntar(api, USUARIO_A, PREGUNTA_A).json()

    segunda = preguntar(api, USUARIO_A, "y el segundo caso?", primera["conversacion_id"])

    assert segunda.status_code == 200
    assert segunda.json()["conversacion_id"] == primera["conversacion_id"]
    assert PREGUNTA_A in json.dumps(modelo.llamadas[-1]["mensajes"], ensure_ascii=False)


# ---- Ejemplos entre empresas ----


def test_el_ejemplo_de_a_no_llega_a_b(api, modelo, sesiones):
    de_a = preguntar(api, USUARIO_A, PREGUNTA_A).json()
    voto = api.post(f"/api/v1/indira/mensajes/{de_a['mensaje_id']}/feedback", json={"feedback": "positivo"})
    assert voto.status_code == 200
    # Y tampoco una fila antigua de cuando el feedback si llenaba la tabla.
    with sesiones() as db:
        db.add(EjemploVerificado(pregunta_usuario=PREGUNTA_A, respuesta_indira="dato antiguo de la empresa A"))
        db.commit()
    modelo.llamadas.clear()

    r = preguntar(api, USUARIO_B, PREGUNTA_A)

    assert r.status_code == 200
    recibido = modelo.texto_recibido()
    assert RESPUESTA_A not in recibido
    assert "dato antiguo de la empresa A" not in recibido
    # Solo el prompt de sistema y la pregunta de B.
    assert [m["role"] for m in modelo.llamadas[0]["mensajes"]] == ["system", "user"]


def test_el_feedback_positivo_ya_no_crea_ejemplos(api, modelo, sesiones):
    de_a = preguntar(api, USUARIO_A, PREGUNTA_A).json()

    api.post(f"/api/v1/indira/mensajes/{de_a['mensaje_id']}/feedback", json={"feedback": "positivo"})

    assert contar(sesiones, EjemploVerificado) == 0
    with sesiones() as db:
        assert db.get(MensajeIndira, uuid.UUID(de_a["mensaje_id"])).feedback == FeedbackMensaje.POSITIVO


# ---- Feedback con y sin usuario ----


def test_feedback_con_usuario_ajeno_responde_404_y_no_marca(api, modelo, sesiones):
    de_a = preguntar(api, USUARIO_A).json()

    r = api.post(
        f"/api/v1/indira/mensajes/{de_a['mensaje_id']}/feedback",
        json={"feedback": "negativo", "usuario_id": USUARIO_B},
    )

    assert r.status_code == 404
    with sesiones() as db:
        assert db.get(MensajeIndira, uuid.UUID(de_a["mensaje_id"])).feedback is None


def test_feedback_del_dueno_y_del_backend_que_aun_no_envia_usuario(api, modelo):
    de_a = preguntar(api, USUARIO_A).json()
    url = f"/api/v1/indira/mensajes/{de_a['mensaje_id']}/feedback"

    assert api.post(url, json={"feedback": "positivo", "usuario_id": USUARIO_A}).status_code == 200
    assert api.post(url, json={"feedback": "negativo"}).status_code == 200


# ---- Llamadas reales del cliente de Ollama, sin servidor ----


@pytest.fixture
def ollama_de_prueba(monkeypatch):
    """Usa el cliente real de ollama contra un transporte falso: se ve lo que saldria por la red."""
    estado = {"peticiones": [], "respuestas": [], "timeouts": []}

    def manejador(request):
        estado["peticiones"].append(json.loads(request.content))
        return httpx.Response(200, json={"model": "m", "message": estado["respuestas"].pop(0), "done": True})

    cliente_real = ollama.Client

    def fabrica(host=None, timeout=None):
        estado["timeouts"].append(timeout)
        return cliente_real(host=host, timeout=timeout, transport=httpx.MockTransport(manejador))

    monkeypatch.setattr(llm_client.ollama, "Client", fabrica)
    return estado


def test_tool_calls_se_reenvian_al_modelo(api, ollama_de_prueba, monkeypatch, sesiones):
    monkeypatch.setattr(service, "ejecutar_herramienta", lambda *a: {"encontrado": False, "mensaje": "nada"})
    llamada = {"function": {"name": "consultar_persona", "arguments": {"nombre_o_documento": "Rosa"}}}
    ollama_de_prueba["respuestas"] = [
        {"role": "assistant", "content": "", "tool_calls": [llamada]},
        {"role": "assistant", "content": "No encontre a Rosa."},
    ]

    r = preguntar(api, USUARIO_A, "busca a Rosa")

    assert r.status_code == 200 and r.json()["respuesta"].startswith("No encontre a Rosa.")
    segunda = ollama_de_prueba["peticiones"][1]["messages"]
    assert [m["role"] for m in segunda][-2:] == ["assistant", "tool"]
    assert segunda[-2]["tool_calls"] == [llamada]
    assert segunda[-1]["tool_name"] == "consultar_persona"


def test_num_ctx_y_timeout_salen_de_la_configuracion(api, ollama_de_prueba, monkeypatch):
    monkeypatch.setattr(settings, "OLLAMA_NUM_CTX", 2222)
    monkeypatch.setattr(settings, "OLLAMA_TIMEOUT_SEGUNDOS", 77)
    ollama_de_prueba["respuestas"] = [{"role": "assistant", "content": "ok"}]

    assert preguntar(api, USUARIO_A).status_code == 200

    assert ollama_de_prueba["peticiones"][0]["options"]["num_ctx"] == 2222
    assert 0 < ollama_de_prueba["timeouts"][0] <= 77


def test_la_vigilancia_usa_el_mismo_num_ctx_que_el_chat(monkeypatch):
    monkeypatch.setattr(settings, "OLLAMA_NUM_CTX", 2222)
    peticiones = []

    def manejador(request):
        peticiones.append(json.loads(request.content))
        return httpx.Response(
            200, json={"model": "m", "message": {"role": "assistant", "content": "{}"}, "done": True}
        )

    cliente_real = ollama.Client
    monkeypatch.setattr(
        deteccion_casos.ollama,
        "Client",
        lambda host=None: cliente_real(host=host, transport=httpx.MockTransport(manejador)),
    )

    deteccion_casos.detectar_caso_en_texto(Persona(nombres="Rosa", apellidos="Quispe"), "titulo", "texto")

    assert peticiones[0]["options"]["num_ctx"] == 2222


def test_si_ollama_vence_el_plazo_responde_503(api, monkeypatch):
    def manejador(request):
        raise httpx.ReadTimeout("sin respuesta", request=request)

    cliente_real = ollama.Client
    monkeypatch.setattr(
        llm_client.ollama,
        "Client",
        lambda host=None, timeout=None: cliente_real(host=host, timeout=timeout, transport=httpx.MockTransport(manejador)),
    )

    assert preguntar(api, USUARIO_A).status_code == 503


def test_el_plazo_es_de_todo_el_turno_y_no_de_cada_pasada(api, monkeypatch):
    monkeypatch.setattr(service, "ejecutar_herramienta", lambda *a: {"encontrado": False})
    monkeypatch.setattr(settings, "OLLAMA_TIMEOUT_SEGUNDOS", 100)
    reloj = {"ahora": 0.0}
    monkeypatch.setattr(service.time, "monotonic", lambda: reloj["ahora"])
    plazos = []

    def modelo_lento(mensajes, herramientas=None, timeout=None):
        plazos.append(timeout)
        reloj["ahora"] += 60
        return ollama.Message(
            role="assistant",
            content="",
            tool_calls=[{"function": {"name": "consultar_persona", "arguments": {"nombre_o_documento": "x"}}}],
        )

    monkeypatch.setattr(service, "generar_respuesta", modelo_lento)

    assert preguntar(api, USUARIO_A).status_code == 503
    assert plazos == [100, 40]


# ---- Ventana de historial y tamano del mensaje ----


def test_el_modelo_recibe_solo_la_ventana_mas_reciente(api, modelo, sesiones, monkeypatch):
    monkeypatch.setattr(settings, "INDIRA_VENTANA_HISTORIAL", 6)
    base = datetime.now(timezone.utc) - timedelta(days=1)
    with sesiones() as db:
        conversacion = ConversacionIndira(usuario_id=uuid.UUID(USUARIO_A), canal=CanalConversacion.WEB)
        db.add(conversacion)
        db.flush()
        for i in range(30):
            rol = RolMensaje.USER if i % 2 == 0 else RolMensaje.ASSISTANT
            db.add(
                MensajeIndira(
                    conversacion_id=conversacion.id,
                    rol=rol,
                    contenido=f"mensaje-{i:02d}",
                    creado_en=base + timedelta(minutes=i),
                )
            )
        db.commit()
        conversacion_id = str(conversacion.id)

    assert preguntar(api, USUARIO_A, "la ultima", conversacion_id).status_code == 200

    enviados = modelo.llamadas[0]["mensajes"]
    # El mas antiguo que cabia era una respuesta suelta (mensaje-25): se omite.
    assert [m["content"] for m in enviados[1:]] == [
        "mensaje-26",
        "mensaje-27",
        "mensaje-28",
        "mensaje-29",
        "la ultima",
    ]
    assert enviados[1]["role"] == "user"


def test_un_mensaje_de_mas_de_2000_caracteres_se_rechaza(api, modelo):
    assert preguntar(api, USUARIO_A, "x" * 2001).status_code == 422
    assert preguntar(api, USUARIO_A, "x" * 2000).status_code == 200
    assert len(modelo.llamadas) == 1
