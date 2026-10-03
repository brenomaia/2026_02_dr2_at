import pytest

from routes.auth import sign_in_attempts


@pytest.fixture(autouse=True)
def reset_sign_in_rate_limit():
    sign_in_attempts.clear()
    yield
    sign_in_attempts.clear()
