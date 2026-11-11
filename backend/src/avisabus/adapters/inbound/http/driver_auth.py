"""`current_session`: the open shift of the bearer token (driver_session AC-04)."""

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from avisabus.adapters.inbound.http.container import DriverUseCases
from avisabus.domain.errors import InvalidSessionError
from avisabus.domain.models.driver import DriverSession

_bearer = HTTPBearer(
    auto_error=False, description="`session_token` returned by `POST /driver/sessions`."
)


def driver_use_cases(request: Request) -> DriverUseCases:
    use_cases: DriverUseCases = request.app.state.driver_use_cases
    return use_cases


async def current_session(
    use_cases: Annotated[DriverUseCases, Depends(driver_use_cases)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> DriverSession:
    """Raises `InvalidSessionError` when the token is missing or is not of an open shift."""
    if credentials is None:
        raise InvalidSessionError()
    return await use_cases.authenticate.execute(credentials.credentials)
