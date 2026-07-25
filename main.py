from typing import Annotated

import typer
import uvicorn

from app.config import settings

cli = typer.Typer(add_completion=False, help="Run the morning-dust dashboard server.")


@cli.command()
def main(
    host: Annotated[
        str, typer.Option("--host", help="Interface to bind. 0.0.0.0 serves the whole LAN.")
    ] = settings.host,
    port: Annotated[int, typer.Option("--port", "-p", help="Port to listen on.")] = settings.port,
    reload: Annotated[
        bool, typer.Option("--reload/--no-reload", help="Restart on code changes.")
    ] = settings.debug,
) -> None:
    """Start the server. Defaults come from .env (MORNING_DUST_HOST, _PORT,
    _DEBUG); these options override them for a single run."""
    uvicorn.run("app.main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    cli()
