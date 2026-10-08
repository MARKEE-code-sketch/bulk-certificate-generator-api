"""Application factory and default ASGI application."""

from contextlib import asynccontextmanager
from pathlib import Path
import os
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.certificate_generator import generate_certificate
from app.database import create_database, initialize_database
from app.job_service import JobService
from app.routes import router


def create_app(
    database_url: str | None = None,
    output_dir: str | Path | None = None,
) -> FastAPI:
    """Build the API, allowing tests to supply isolated database and file paths."""
    engine, session_factory = create_database(database_url)

    certificate_dir = Path(
        output_dir or os.getenv("CERTIFICATE_OUTPUT_DIR", "data/certificates")
    )

    @asynccontextmanager
    async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
        initialize_database(engine)
        certificate_dir.mkdir(parents=True, exist_ok=True)
        try:
            yield
        finally:
            engine.dispose()

    application = FastAPI(
        title="Bulk Certificate Generator API",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.state.engine = engine
    application.state.session_factory = session_factory
    application.state.job_service = JobService(
        session_factory=session_factory,
        output_dir=certificate_dir,
        renderer=generate_certificate,
    )
    application.include_router(router)
    return application


app = create_app()
