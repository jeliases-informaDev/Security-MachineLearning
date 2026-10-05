import enum


class TipoDocumento(str, enum.Enum):
    DNI = "DNI"
    RUC = "RUC"
    CE = "CE"
    PASAPORTE = "PASAPORTE"


class OrigenPersona(str, enum.Enum):
    KOTLIN_SYNC = "kotlin_sync"
    SCRAPER_DETECTADO = "scraper_detectado"


class EstadoVerificacion(str, enum.Enum):
    PENDIENTE = "pendiente"
    VERIFICADO = "verificado"
    DESCARTADO = "descartado"


class TipoCaso(str, enum.Enum):
    ACUSACION = "acusacion"
    DENUNCIA = "denuncia"
    INVESTIGACION = "investigacion"
    SENTENCIA = "sentencia"
    ABSOLUCION = "absolucion"


class EstadoRevision(str, enum.Enum):
    PENDIENTE = "pendiente"
    VERIFICADO = "verificado"
    DESCARTADO = "descartado"


class CanalTicket(str, enum.Enum):
    CHAT_INDIRA = "chat_indira"
    WEB = "web"
    APP = "app"


class TipoTicket(str, enum.Enum):
    CONSULTA = "consulta"
    REPORTE = "reporte"
    SOPORTE = "soporte"
    RECLAMO = "reclamo"


class EstadoTicket(str, enum.Enum):
    ABIERTO = "abierto"
    EN_PROCESO = "en_proceso"
    RESUELTO = "resuelto"
    CERRADO = "cerrado"


class PrioridadTicket(str, enum.Enum):
    BAJA = "baja"
    MEDIA = "media"
    ALTA = "alta"


class CreadoPorTicket(str, enum.Enum):
    USUARIO = "usuario"
    INDIRA = "indira"


class AutorMensajeTicket(str, enum.Enum):
    USUARIO = "usuario"
    INDIRA = "indira"
    AGENTE_HUMANO = "agente_humano"


class CanalConversacion(str, enum.Enum):
    WEB = "web"
    APP = "app"


class EstadoConversacion(str, enum.Enum):
    ACTIVA = "activa"
    CERRADA = "cerrada"


class RolMensaje(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class FormatoReporte(str, enum.Enum):
    PDF = "pdf"
    XLSX = "xlsx"
    JSON = "json"


class FeedbackMensaje(str, enum.Enum):
    POSITIVO = "positivo"
    NEGATIVO = "negativo"
