import numpy as np
import pytest

from topospec.data.synthetic import generate_building, generate_corpus


@pytest.fixture
def rng():
    return np.random.default_rng(7)


@pytest.fixture
def building(rng):
    return generate_building(rng, "syn:test", n_rooms=20, n_corridors=4, n_zones=4)


@pytest.fixture
def corpus(rng):
    return generate_corpus(rng, n_buildings=16)
