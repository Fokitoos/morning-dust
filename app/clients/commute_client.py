class CommuteClient:
    """Thin wrapper around a routing provider (e.g. Google Maps Directions)."""

    def fetch_route(self, origin: str, destination: str) -> dict:
        raise NotImplementedError
