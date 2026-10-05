import re
import unicodedata

from app.models.persona import Persona


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes ni signos de puntuación y con espacios simples.

    "Cerrón, Vladimir" -> "cerron vladimir". Se usa en ambos lados de cada
    comparación, así que da igual cómo escriba cada diario el nombre.
    """
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", sin_tildes.lower()).split())


def aparece_en(texto_normalizado: str, variante_normalizada: str) -> bool:
    """True si la variante aparece como palabra completa (no dentro de otra palabra)."""
    if not variante_normalizada:
        return False
    return re.search(rf"\b{re.escape(variante_normalizada)}\b", texto_normalizado) is not None


_PARTICULAS = {"de", "del", "la", "las", "los", "san", "santa"}


def primer_apellido(persona: Persona) -> str:
    """Primer apellido normalizado ("Concepción Carhuancho" -> "concepcion").

    Algunos registros guardan apellidos compuestos como "de Soto" o "Lopez Aliaga":
    si empieza con una partícula se conserva junto al apellido que le sigue.
    """
    partes = normalizar(persona.apellidos).split()
    if not partes:
        return ""
    if partes[0] in _PARTICULAS and len(partes) > 1:
        return " ".join(partes[:2])
    return partes[0]


def nombre_para_busqueda(persona: Persona) -> str:
    """Primer nombre + primer apellido tal como están escritos (con tildes), para la consulta."""
    nombres = persona.nombres.split()
    apellidos = persona.apellidos.split()
    if not apellidos:
        return " ".join(nombres[:1])
    particula = normalizar(apellidos[0]) in _PARTICULAS and len(apellidos) > 1
    return " ".join([*nombres[:1], *apellidos[: 2 if particula else 1]])


def nombre_comun(persona: Persona) -> str:
    """Primer nombre + primer apellido, que es como suelen escribirlo los diarios."""
    partes = normalizar(persona.nombres).split()
    primer_nombre = partes[0] if partes else ""
    return f"{primer_nombre} {primer_apellido(persona)}".strip()


def variantes_nombre(persona: Persona) -> list[str]:
    """Formas normalizadas con las que se puede nombrar a la persona en una noticia.

    No incluye el apellido solo: es demasiado ambiguo para decidir que una noticia
    habla de esta persona ("Castillo" puede ser cualquiera).
    """
    candidatas = [
        f"{persona.nombres} {persona.apellidos}",
        nombre_comun(persona),
        *(persona.nombres_alternativos or []),
    ]
    variantes: list[str] = []
    for candidata in candidatas:
        normalizada = normalizar(candidata)
        if normalizada and normalizada not in variantes:
            variantes.append(normalizada)
    return variantes


def se_menciona(texto: str, persona: Persona) -> bool:
    """True si el texto nombra a la persona por alguna de sus variantes."""
    texto_normalizado = normalizar(texto)
    return any(aparece_en(texto_normalizado, v) for v in variantes_nombre(persona))


# Palabras que pueden ir pegadas delante de un apellido sin ser otro nombre propio
# ("Presidenta Boluarte", "Expresidente Vizcarra"). Normalizadas, sin tildes.
TITULOS = {
    "presidente", "presidenta", "expresidente", "expresidenta", "ministro", "ministra", "exministro", "exministra",
    "premier", "expremier", "congresista", "excongresista", "fiscal", "exfiscal", "gobernador", "gobernadora",
    "exgobernador", "exgobernadora", "alcalde", "alcaldesa", "exalcalde", "exalcaldesa", "candidato", "candidata",
    "lider", "jefe", "jefa", "magistrado", "magistrada", "juez", "jueza", "general", "coronel", "senor", "senora",
    "sr", "sra", "dr", "dra", "don", "dona", "exmandatario", "exmandataria", "mandatario", "mandataria",
}

_TOKEN = re.compile(r"[^\W\d_]+|\S")


def apellido_sin_otro_nombre(titulo: str, apellido_normalizado: str) -> bool:
    """True si el apellido aparece en el titular SIN otro nombre propio pegado delante.

    Los titulares abrevian ("Boluarte: Fiscalía abre investigación"), así que el apellido
    solo sirve, pero únicamente si no es de otra persona: en "pedido de Óscar Acuña" el
    apellido va detrás de otro nombre propio y no se refiere a César Acuña.
    """
    if not apellido_normalizado:
        return False
    tokens = _TOKEN.findall(titulo)
    partes = apellido_normalizado.split()
    for i in range(len(tokens)):
        if [normalizar(t) for t in tokens[i : i + len(partes)]] != partes:
            continue
        previo = tokens[i - 1] if i > 0 else ""
        if not previo or not previo[0].isalpha() or previo[0].islower():
            return True  # inicio de titular, puntuación ("Boluarte:") o palabra común ("el", "de", "para")
        if normalizar(previo) in TITULOS:
            return True
        # Empieza con mayúscula y no es un título: casi seguro otro nombre propio.
    return False


def menciona_persona(titulo: str, descripcion: str, persona: Persona) -> bool:
    """La nota habla de esta persona: la nombra completa (en título o resumen) o, en el
    titular, por un apellido que no pertenece a otra persona."""
    texto = normalizar(f"{titulo} {descripcion}")
    if any(aparece_en(texto, v) for v in variantes_nombre(persona)):
        return True
    return apellido_sin_otro_nombre(titulo, primer_apellido(persona))
