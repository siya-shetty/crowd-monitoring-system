import os
from app.crowd.schemas import CrowdConfig


def from_environment() -> CrowdConfig:
    names = {"moderate_count": "CROWD_MODERATE_COUNT", "high_count": "CROWD_HIGH_COUNT",
             "very_high_count": "CROWD_VERY_HIGH_COUNT"}
    return CrowdConfig(**{key: os.environ[name] for key, name in names.items() if name in os.environ})
