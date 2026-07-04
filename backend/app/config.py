from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://stonewall:change_me_local_dev@db:5432/stonewall"
    image_dir: str = "/data/images"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
