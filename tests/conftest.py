import pytest

from src.runtime import Runtime
from src.simulation import SimClock, demo_config


@pytest.fixture
def clock():
    return SimClock()


@pytest.fixture
def runtime(clock):
    rt = Runtime(demo_config(), clock.monotonic, clock.wall)
    yield rt
    rt.close()
