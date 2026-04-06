from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    github_token: str
    github_owner: str
    github_repo: str

    installer_dir: str = "/data/installers"
    installer_ttl_hours: int = 72


settings = Settings()  # type: ignore[call-arg]
