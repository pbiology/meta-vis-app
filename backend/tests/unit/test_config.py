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

    # No explicit override — value comes from backend/.env.dev (committed
    # dev defaults). There is no longer a code-level localhost fallback;
    # required keys missing from both env and env files raise ValidationError.
    settings = Settings()
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    assert origins == ["http://localhost:5173"]


def test_missing_required_keys_raises():
    """Settings must fail loud when required keys aren't supplied."""
    import pytest
    from pydantic import ValidationError

    # No env_file, no env kwargs — keycloak_issuer, cors_origins, and Mongo
    # config are all missing. Pydantic raises before our validator runs.
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_mongo_config_validator():
    """Either MONGODB_URI alone, or MONGODB_HOST + MONGODB_DB_NAME."""
    import pytest
    from pydantic import ValidationError

    base = {
        "_env_file": None,
        "keycloak_issuer": "https://kc.example/realms/x",
        "cors_origins": "https://app.example",
        "jwt_secret": "x" * 32,
    }

    # URI alone (with db_name) — OK.
    Settings(**base, mongodb_uri="mongodb://h/db", mongodb_db_name="db")  # type: ignore[arg-type]

    # Host + db_name — OK.
    Settings(**base, mongodb_host="h", mongodb_db_name="db")  # type: ignore[arg-type]

    # Neither — raises.
    with pytest.raises(ValidationError):
        Settings(**base)  # type: ignore[arg-type]

    # URI but no db_name — raises (app still reads db_name directly).
    with pytest.raises(ValidationError):
        Settings(**base, mongodb_uri="mongodb://h/db")  # type: ignore[arg-type]
