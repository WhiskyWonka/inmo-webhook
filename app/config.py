from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    verify_token: str = ""
    leads_log_path: str = "/app/data/leads.log"
