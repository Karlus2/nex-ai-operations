from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Set

INSECURE_DEFAULT_SECRETS: Set[str] = {
    "nex_internal_dev_secret_replace_in_prod",
    "secret",
    "changeme",
    "123456",
    "password",
    ""
}

class Settings(BaseSettings):
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DATABASE_URL: str = "sqlite:///./nex.db"
    INTERNAL_API_KEY: str
    N8N_WEBHOOK_TRIAGE_URL: str = "http://localhost:5678/webhook/nex-wf01-triage"
    N8N_WEBHOOK_ACTION_URL: str = "http://localhost:5678/webhook/nex-wf02-action"
    GEMINI_API_KEY: str = ""
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    DEMO_MODE: bool = True  # Define se o ambiente opera com operador demonstrativo local
    REQUIRE_N8N: bool = True

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
