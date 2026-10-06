def agregar_fuentes(respuesta: str, casos: list[dict]) -> str:
    """Agrega al final de la respuesta los enlaces de los casos consultados que el modelo omitió.

    El modelo local no cumple de forma fiable la instrucción de citar cada enlace, y cada caso
    DEBE poder rastrearse a la nota original del diario; por eso se garantiza aquí, en código,
    y no solo en el prompt. Si el modelo ya incluyó un enlace, no se repite.
    """
    pendientes: list[dict] = []
    vistos: set[str] = set()
    for caso in casos:
        url = caso.get("url_fuente")
        if not url or url in respuesta or url in vistos:
            continue
        vistos.add(url)
        pendientes.append(caso)

    if not pendientes:
        return respuesta

    lineas = []
    for caso in pendientes:
        diario = caso.get("diario") or "Diario"
        fecha = caso.get("fecha_publicacion")
        etiqueta = f"{diario} ({fecha})" if fecha else diario
        lineas.append(f"- {etiqueta}: {caso['url_fuente']}")

    return f"{respuesta.rstrip()}\n\nFuentes consultadas:\n" + "\n".join(lineas)
