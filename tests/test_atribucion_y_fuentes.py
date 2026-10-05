import unittest

from app.agent.indira.fuentes import agregar_fuentes
from app.ml_engine.deteccion_casos import es_solo_vinculado, motivo_de_descarte
from app.models.persona import Persona


def persona(nombres: str, apellidos: str) -> Persona:
    return Persona(nombres=nombres, apellidos=apellidos, nombres_alternativos=[])


class TestPersonaSoloVinculada(unittest.TestCase):
    def test_caso_del_exministro_no_es_de_su_jefa(self):
        # Caso real: el caso es de Santiváñez; Boluarte solo es su exjefa.
        titulo = (
            "Fiscalía pide 7 años de cárcel para Juan José Santiváñez: ¿Cuáles son los argumentos "
            "contra el exministro de Dina Boluarte?"
        )
        self.assertTrue(es_solo_vinculado(titulo, persona("Dina", "Boluarte")))
        self.assertEqual(
            motivo_de_descarte(titulo, "", persona("Dina", "Boluarte")),
            "la persona solo aparece como allegado de otro",
        )

    def test_el_familiar_no_es_la_persona(self):
        self.assertTrue(es_solo_vinculado("Investigan al hermano de Dina Boluarte por presunta usurpación", persona("Dina", "Boluarte")))
        self.assertTrue(es_solo_vinculado("Fiscalía cita a la esposa de Ollanta Humala", persona("Ollanta", "Humala")))

    def test_la_persona_misma_si_es_caso(self):
        p = persona("Dina", "Boluarte")
        self.assertFalse(es_solo_vinculado("Fiscalía archiva investigación contra Dina Boluarte", p))
        self.assertFalse(es_solo_vinculado("Fiscalía acusa a Dina Boluarte y a su exministro del Interior", p))
        self.assertIsNone(motivo_de_descarte("Fiscalía archiva investigación contra Dina Boluarte", "", p))

    def test_el_gobierno_de_alguien_es_solo_una_referencia_de_epoca(self):
        # Caso real: el juicio es del exministro Ayala, no de Pedro Castillo.
        titulo = "Exministro Walter Ayala irá a juicio oral por ascensos irregulares en el gobierno de Pedro Castillo"
        self.assertTrue(es_solo_vinculado(titulo, persona("Pedro", "Castillo")))

    def test_si_el_titular_no_la_nombra_no_decide(self):
        # La mención podría estar solo en el cuerpo: otros filtros deciden.
        self.assertFalse(es_solo_vinculado("Fiscalía pide 7 años de cárcel para exministro", persona("Dina", "Boluarte")))

    def test_ambos_roles_se_conservan(self):
        # Nadine Heredia es la esposa de Humala: la nota es de Heredia, no de Humala.
        titulo = "Nadine Heredia, esposa de Ollanta Humala, rinde declaración ante la fiscalía"
        self.assertFalse(es_solo_vinculado(titulo, persona("Nadine", "Heredia")))
        self.assertTrue(es_solo_vinculado(titulo, persona("Ollanta", "Humala")))


class TestSujetoDelCaso(unittest.TestCase):
    """El modelo dice quién es el sujeto del caso; el código verifica que sea la persona vigilada."""

    def respuesta(self, sujeto: str):
        import json
        from types import SimpleNamespace
        from unittest.mock import patch

        from app.ml_engine import deteccion_casos

        contenido = json.dumps(
            {"es_caso": True, "sujeto": sujeto, "tipo": "investigacion", "categoria_delito": "corrupcion", "resumen": "r"}
        )
        falso = SimpleNamespace(chat=lambda **_: SimpleNamespace(message=SimpleNamespace(content=contenido)))
        with patch.object(deteccion_casos.ollama, "Client", return_value=falso):
            return deteccion_casos.detectar_caso_en_texto(
                persona("Delia", "Espinoza"), "titulo", "texto"
            )

    def test_el_sujeto_es_la_persona(self):
        self.assertIsNotNone(self.respuesta("Delia Espinoza"))
        self.assertIsNotNone(self.respuesta("Espinoza"))

    def test_el_sujeto_es_otra_persona(self):
        # Caso real: la investigación era contra los jueces; Delia Espinoza era la beneficiaria.
        self.assertIsNone(self.respuesta("jueces del Poder Judicial"))
        self.assertIsNone(self.respuesta("Fernando Rospigliosi"))
        self.assertIsNone(self.respuesta("Óscar Espinoza"))

    def test_sin_sujeto_no_hay_caso(self):
        self.assertIsNone(self.respuesta(""))


class TestFuentesEnLaRespuestaDeIndira(unittest.TestCase):
    CASOS = [
        {"url_fuente": "https://elcomercio.pe/politica/a/", "diario": "El Comercio", "fecha_publicacion": "2026-10-04"},
        {"url_fuente": "https://gestion.pe/peru/b/", "diario": "Gestión", "fecha_publicacion": None},
    ]

    def test_agrega_los_enlaces_que_el_modelo_omitio(self):
        respuesta = agregar_fuentes("Hay dos casos reportados por la prensa.", self.CASOS)
        self.assertTrue(respuesta.startswith("Hay dos casos reportados por la prensa."))
        self.assertIn("Fuentes consultadas:", respuesta)
        self.assertIn("- El Comercio (2026-10-04): https://elcomercio.pe/politica/a/", respuesta)
        self.assertIn("- Gestión: https://gestion.pe/peru/b/", respuesta)

    def test_no_repite_los_enlaces_que_el_modelo_ya_puso(self):
        respuesta = agregar_fuentes("Caso 1: https://elcomercio.pe/politica/a/", self.CASOS)
        self.assertEqual(respuesta.count("https://elcomercio.pe/politica/a/"), 1)
        self.assertIn("https://gestion.pe/peru/b/", respuesta)

    def test_sin_faltantes_no_cambia_nada(self):
        original = "Caso 1: https://elcomercio.pe/politica/a/ y caso 2: https://gestion.pe/peru/b/"
        self.assertEqual(agregar_fuentes(original, self.CASOS), original)

    def test_sin_casos_no_agrega_nada(self):
        self.assertEqual(agregar_fuentes("Hola, ¿en qué te ayudo?", []), "Hola, ¿en qué te ayudo?")

    def test_ignora_casos_sin_enlace_y_duplicados(self):
        casos = [{"url_fuente": None}, {"url_fuente": "https://rpp.pe/x"}, {"url_fuente": "https://rpp.pe/x"}]
        respuesta = agregar_fuentes("Respuesta", casos)
        self.assertEqual(respuesta.count("https://rpp.pe/x"), 1)


if __name__ == "__main__":
    unittest.main()
