import unittest
from types import SimpleNamespace

from app.ml_engine.matching import elegir_persona


def persona(nombres, apellidos, alternativos=()):
    return SimpleNamespace(nombres=nombres, apellidos=apellidos, nombres_alternativos=list(alternativos))


class BusquedaDePersonasTest(unittest.TestCase):
    def setUp(self):
        self.personas = [
            persona("Vladimir", "Cerrón"),
            persona("Ollanta", "Humala"),
            persona("Antauro", "Humala"),
            persona("Rafael", "Lopez Aliaga"),
            persona("Pedro Pablo", "Kuczynski", ["PPK"]),
        ]

    def test_no_distingue_tildes_ni_mayusculas(self):
        self.assertEqual(elegir_persona(self.personas, "cerron").apellidos, "Cerrón")
        self.assertEqual(elegir_persona(self.personas, "CERRÓN").apellidos, "Cerrón")

    def test_nombre_completo_distingue_hermanos(self):
        self.assertEqual(elegir_persona(self.personas, "Antauro Humala").nombres, "Antauro")

    def test_alias(self):
        self.assertEqual(elegir_persona(self.personas, "ppk").apellidos, "Kuczynski")

    def test_sin_coincidencia(self):
        self.assertIsNone(elegir_persona(self.personas, "xyzzy qwerty"))


if __name__ == "__main__":
    unittest.main()
