import unittest

from app.ml_engine.deteccion_casos import ajustar_tipo, es_solo_denunciante
from app.ml_engine.nombres import (
    aparece_en,
    apellido_sin_otro_nombre,
    menciona_persona,
    nombre_para_busqueda,
    normalizar,
    primer_apellido,
    se_menciona,
    variantes_nombre,
)
from app.models.persona import Persona
from app.scraper.google_news import construir_consulta, dominio_de, es_diario_reconocido
from app.services.vigilancia_service import _menciona_a, tiene_tema_judicial


def persona(nombres: str, apellidos: str, alias: list[str] | None = None) -> Persona:
    return Persona(nombres=nombres, apellidos=apellidos, nombres_alternativos=alias or [])


class TestNombres(unittest.TestCase):
    def test_normalizar_quita_tildes_y_signos(self):
        self.assertEqual(normalizar("Cerrón, Vladimir"), "cerron vladimir")
        self.assertEqual(normalizar("  Muñoz   ÁVALOS "), "munoz avalos")

    def test_aparece_en_exige_palabra_completa(self):
        self.assertTrue(aparece_en("keiko fujimori higuchi", "keiko fujimori"))
        self.assertFalse(aparece_en("los castillos de pedro", "castillo"))
        self.assertFalse(aparece_en("cualquier texto", ""))

    def test_primer_apellido_conserva_particulas(self):
        self.assertEqual(primer_apellido(persona("Hernando", "de Soto")), "de soto")
        self.assertEqual(primer_apellido(persona("Richard", "Concepción Carhuancho")), "concepcion")

    def test_nombre_para_busqueda_usa_primer_nombre_y_primer_apellido_con_tildes(self):
        self.assertEqual(nombre_para_busqueda(persona("Vladimir", "Cerrón Rojas")), "Vladimir Cerrón")
        self.assertEqual(nombre_para_busqueda(persona("Pedro Pablo", "Kuczynski")), "Pedro Kuczynski")
        self.assertEqual(nombre_para_busqueda(persona("Hernando", "de Soto Polar")), "Hernando de Soto")

    def test_variantes_incluyen_nombre_comun_y_alias_sin_repetir(self):
        variantes = variantes_nombre(persona("Dina", "Boluarte Zegarra", ["Dina Boluarte", "PPK"]))
        self.assertIn("dina boluarte zegarra", variantes)
        self.assertIn("dina boluarte", variantes)
        self.assertIn("ppk", variantes)
        self.assertEqual(len(variantes), len(set(variantes)))

    def test_se_menciona_ignora_tildes_y_mayusculas(self):
        p = persona("Vladimir", "Cerrón Rojas")
        self.assertTrue(se_menciona("Fiscalía acusa a VLADIMIR CERRON por caso Antalsis", p))
        self.assertFalse(se_menciona("Fiscalía acusa a Vladimir Putin", p))


class TestFiltrosDeVigilancia(unittest.TestCase):
    def test_tema_judicial(self):
        self.assertTrue(tiene_tema_judicial("Fiscalía abre investigación contra el expresidente"))
        self.assertTrue(tiene_tema_judicial("Dictan prisión preventiva"))
        self.assertTrue(tiene_tema_judicial("Condenan a 14 años de cárcel"))
        self.assertFalse(tiene_tema_judicial("Boluarte inaugura puente en Arequipa"))
        # Casos reales de la primera versión: ceses y designaciones no son casos legales.
        self.assertFalse(tiene_tema_judicial("JNJ dispone cese de Zoraida Ávalos como fiscal suprema por límite de edad"))
        self.assertFalse(tiene_tema_judicial("Dan por concluida designación de Zoraida Ávalos en la Primera Fiscalía Suprema Penal"))
        self.assertTrue(tiene_tema_judicial("JNJ destituye a juez por faltas disciplinarias"))
        self.assertTrue(tiene_tema_judicial("Fiscalía formaliza investigación contra el gobernador"))
        self.assertFalse(tiene_tema_judicial("Encuesta: así va la intención de voto"))

    def test_menciona_a_acepta_nombre_o_primer_apellido(self):
        p = persona("Dina", "Boluarte Zegarra")
        self.assertTrue(_menciona_a("Dina Boluarte: fiscalía pide impedimento de salida", p))
        self.assertTrue(_menciona_a("Boluarte: fiscalía pide impedimento de salida", p))
        self.assertFalse(_menciona_a("Fiscalía pide impedimento de salida contra exministro", p))

    def test_solo_diarios_reconocidos(self):
        self.assertTrue(es_diario_reconocido("elcomercio.pe"))
        self.assertTrue(es_diario_reconocido("m.rpp.pe"))
        self.assertTrue(es_diario_reconocido("infobae.com"))
        self.assertFalse(es_diario_reconocido("facebook.com"))
        self.assertFalse(es_diario_reconocido("notrpp.pe"))
        self.assertFalse(es_diario_reconocido("elcomercio.pe.evil.com"))

    def test_dominio_de(self):
        self.assertEqual(dominio_de("https://www.RPP.pe/politica/x"), "rpp.pe")
        self.assertEqual(dominio_de("https://gestion.pe:443/peru/x"), "gestion.pe")
        self.assertEqual(dominio_de(""), "")

    def test_consulta_pide_el_nombre_exacto_y_una_ventana_de_dias(self):
        consulta = construir_consulta("Vladimir Cerrón", 30)
        self.assertTrue(consulta.startswith('"Vladimir Cerrón"'))
        self.assertIn("when:30d", consulta)
        self.assertIn("fiscalía", consulta)


class TestAtribucionALaPersonaCorrecta(unittest.TestCase):
    """Casos reales donde la primera versión atribuyó mal la noticia."""

    def test_apellido_de_otra_persona_no_cuenta(self):
        # "Óscar Acuña" no es César Acuña.
        titulo = "Poder Judicial rechazó nuevamente pedido de Óscar Acuña para ser excluido del caso Frigoinca"
        self.assertFalse(apellido_sin_otro_nombre(titulo, "acuna"))
        self.assertFalse(menciona_persona(titulo, "", persona("César", "Acuña")))

    def test_apellido_suelto_en_titular_si_cuenta(self):
        self.assertTrue(apellido_sin_otro_nombre("Boluarte: fiscalía abre investigación", "boluarte"))
        self.assertTrue(apellido_sin_otro_nombre("Presidenta Boluarte enfrenta nueva denuncia", "boluarte"))
        self.assertTrue(apellido_sin_otro_nombre("Piden prisión preventiva para Vizcarra", "vizcarra"))
        self.assertTrue(apellido_sin_otro_nombre("Fiscalía cita al expresidente Vizcarra", "vizcarra"))
        self.assertTrue(apellido_sin_otro_nombre("Caso Cócteles: «Fujimori» declara", "fujimori"))

    def test_nombre_completo_en_el_resumen_basta(self):
        p = persona("César", "Acuña")
        self.assertTrue(menciona_persona("Poder Judicial admite recurso", "El Poder Judicial admitió el recurso de César Acuña", p))

    def test_el_denunciante_no_es_el_denunciado(self):
        p = persona("César", "Acuña")
        querella = "Poder Judicial admite querella de César Acuña contra Fernando Olivera por presunta difamación"
        self.assertTrue(es_solo_denunciante(querella, p))
        self.assertTrue(es_solo_denunciante("Acuña denuncia a Olivera ante la fiscalía", p))

    def test_quien_presenta_la_denuncia_no_es_el_denunciado(self):
        # Caso real: Mirtha Vásquez presenta la denuncia constitucional contra Josué Gutiérrez.
        titulo = "Mirtha Vásquez presentó segunda denuncia constitucional contra Josué Gutiérrez y pidió inhabilitación"
        self.assertTrue(es_solo_denunciante(titulo, persona("Mirtha", "Vásquez")))
        self.assertFalse(es_solo_denunciante(titulo, persona("Josué", "Gutiérrez")))

    def test_el_denunciado_si_es_caso(self):
        p = persona("César", "Acuña")
        self.assertFalse(es_solo_denunciante("Fiscalía investiga a César Acuña por presunto plagio", p))
        self.assertFalse(es_solo_denunciante("Denuncia contra César Acuña por plagio llega al Poder Judicial", p))
        # Ambos roles en la misma nota: se conserva (podría haber caso contra él).
        self.assertFalse(es_solo_denunciante("Querella de Acuña contra Olivera y denuncia contra Acuña", p))


class TestAjusteDeTipo(unittest.TestCase):
    def test_absolucion_sin_evidencia_baja_a_investigacion(self):
        # Caso real: el modelo marcó "absolucion" para el retiro de una orden de captura.
        texto = "Interpol retira orden internacional de captura contra Vladimir Cerrón"
        self.assertEqual(ajustar_tipo("absolucion", texto), "investigacion")

    def test_absolucion_con_evidencia_se_mantiene(self):
        self.assertEqual(ajustar_tipo("absolucion", "Juez absuelve al exalcalde por falta de pruebas"), "absolucion")

    def test_sentencia_exige_condena_o_sentencia_en_el_texto(self):
        self.assertEqual(ajustar_tipo("sentencia", "Fiscalía pide seis años para el gobernador"), "investigacion")
        self.assertEqual(ajustar_tipo("sentencia", "Condenan a 14 años de cárcel al expresidente"), "sentencia")

    def test_acusacion_exige_la_palabra_acusacion(self):
        self.assertEqual(ajustar_tipo("acusacion", "Poder Judicial rechaza recurso en el caso"), "investigacion")
        self.assertEqual(ajustar_tipo("acusacion", "Fiscalía presenta acusación contra el congresista"), "acusacion")

    def test_tipos_neutros_no_se_tocan(self):
        self.assertEqual(ajustar_tipo("investigacion", "cualquier cosa"), "investigacion")
        self.assertEqual(ajustar_tipo("denuncia", "cualquier cosa"), "denuncia")


if __name__ == "__main__":
    unittest.main()
