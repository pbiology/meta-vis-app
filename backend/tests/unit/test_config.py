from app.config import Settings


def test_cors_origins_parsing():
    """Test that CORS origins are parsed correctly from comma-separated string."""
    # Test single origin
    settings = Settings(cors_origins="http://localhost:5173")
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    assert origins == ["http://localhost:5173"]

    # Test multiple origins
    settings = Settings(cors_origins="http://localhost:5173,https://example.com")
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    assert origins == ["http://localhost:5173", "https://example.com"]

    # Test with whitespace
    settings = Settings(
        cors_origins="http://localhost:5173, https://example.com , https://another.com"
    )
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    assert origins == [
        "http://localhost:5173",
        "https://example.com",
        "https://another.com",
    ]

    # Test default
    settings = Settings()
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    assert origins == ["http://localhost:5173"]
