from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_name: str = 'OpsPilot MVP'
    environment: str = 'dev'

    # LLM
    gemini_api_key: str | None = None
    gemini_model: str = 'gemini-1.5-flash'

    # basic governance knobs (MVP)
    require_change_id_for_prod: bool = True
    patch_cutoff_hours: int = 24
    bulk_threshold: int = 30

    # demo auth
    demo_users_json: str = '{"admin": {"role": "admin"}, "operator": {"role": "operator"}, "viewer": {"role": "viewer"}}'


settings = Settings()
