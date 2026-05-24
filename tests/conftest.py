from collections.abc import Iterator
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.deps import get_current_employee
from app.main import app


@pytest.fixture(autouse=True)
def override_current_employee(request: pytest.FixtureRequest) -> Iterator[None]:
    if request.node.get_closest_marker("no_auth_override") is not None:
        app.dependency_overrides.pop(get_current_employee, None)
        yield
        return

    async def fake_current_employee() -> SimpleNamespace:
        return SimpleNamespace(id=uuid4(), role="admin")

    app.dependency_overrides[get_current_employee] = fake_current_employee
    yield
    app.dependency_overrides.pop(get_current_employee, None)
