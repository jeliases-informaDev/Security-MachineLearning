from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # "dev" permite llamar a la API sin clave interna; cualquier otro valor la exige.
    ENTORNO: str = "dev"

    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/security_ml"

    # Clave compartida con el backend Kotlin (header X-Internal-Key). El ML no debe
    # exponerse directamente al frontend: solo el backend Kotlin lo consume.
    INTERNAL_API_KEY: str = ""

    # Orígenes permitidos por CORS, separados por coma.
    ALLOWED_ORIGINS: str = "http://localhost:8081"

    # Permite apagar a Indira (responde 503) si todavía no hay un modelo disponible.
    INDIRA_ENABLED: bool = True

    # Modelo local autohospedado para el agente Indira (ver docs/ARQUITECTURA.md)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:8b"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]


settings = Settings()
