from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    twelvedata_api_key: str
    twelvedata_base_url: str = "https://api.twelvedata.com"
    # Free tier: 8 calls/min, 800 credits/day
    twelvedata_max_calls_per_minute: int = 8

    model_config = {"env_file": ".env"}


settings = Settings()
