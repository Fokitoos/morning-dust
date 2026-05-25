from app.schemas.commute import CommuteResponse


class CommuteService:
    def get_current(self) -> CommuteResponse:
        return CommuteResponse(
            origin="",
            destination="",
            duration_minutes=0,
            traffic="unknown",
        )


def get_commute_service() -> CommuteService:
    return CommuteService()
