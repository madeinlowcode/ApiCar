import pytest
import yaml
from pathlib import Path

SNAPSHOTS_DIR = Path(__file__).parent.parent / "snapshots"


@pytest.fixture
def homepage_snapshot():
    with open(SNAPSHOTS_DIR / "homepage-snapshot.yaml") as f:
        return yaml.safe_load(f)


@pytest.fixture
def vw_models_snapshot():
    with open(SNAPSHOTS_DIR / "vw-models-snapshot.yaml") as f:
        return yaml.safe_load(f)


@pytest.fixture
def vw_golf_variants_snapshot():
    with open(SNAPSHOTS_DIR / "vw-golf-variants-snapshot.yaml") as f:
        return yaml.safe_load(f)


@pytest.fixture
def vw_golf_parts_snapshot():
    with open(SNAPSHOTS_DIR / "vw-golf-parts-snapshot.yaml") as f:
        return yaml.safe_load(f)


@pytest.fixture
def vw_golf_engine_snapshot():
    with open(SNAPSHOTS_DIR / "vw-golf-engine-snapshot.yaml") as f:
        return yaml.safe_load(f)


@pytest.fixture
def vw_golf_parts_detail_snapshot():
    with open(SNAPSHOTS_DIR / "vw-golf-parts-detail-snapshot.yaml") as f:
        return yaml.safe_load(f)
