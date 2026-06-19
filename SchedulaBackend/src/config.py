from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Database settings
    database_url: str = "postgresql://postgres:postgres@localhost:5432/schedula"
    database_pool_min_size: int = 10
    database_pool_max_size: int = 20
    
    # RabbitMQ settings
    rabbitmq_url: str = "amqp://rabbitmq:rabbitmq@localhost:5672/"
    notification_queue_name: str = "notifications_queue"
    
    # Ollama settings
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "deepseek-r1:7b"

    # University provider settings (Ollama-compatible endpoint)
    university_url: str = "https://132.73.84.84"
    university_verify_ssl: bool = False

    # LLM Provider settings
    llm_provider: str = "ollama"  # Options: "ollama", "groq", "university"

    # Groq settings
    groq_api_key: str | None = None
    groq_model: str = "llama-3.1-8b-instant"

    # Application settings
    app_name: str = "SchedulaBackend"
    debug: bool = False
    enable_dev_routes: bool = True
    
    # Notification service communication
    notification_service_base_url: str = "http://notification:8000"

    # Public URL of the Schedula web app, embedded in lecturer notifications
    # so recipients can open the app directly from email/Telegram.
    frontend_base_url: str = "https://schedula.local"

    # # --- JWT Settings (MUST BE ADDED) ---
    SECRET_KEY: str = "631b209e0e661ede399d3e15073ff3ce87b377180bd338c755b0683339b534e5"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # #
    # model_config = SettingsConfigDict(
    #     env_file=".env",
    #     env_file_encoding="utf-8",
    #     case_sensitive=False
    # )


# Global settings instance
settings = Settings()
