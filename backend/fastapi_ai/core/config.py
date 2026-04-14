from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Glunova FastAPI AI"
    jwt_shared_secret: str = "dev-secret"
    jwt_algorithm: str = "HS256"
    database_url: str = "postgresql+psycopg://glunova:glunova@localhost:5432/glunova"


settings = Settings()
