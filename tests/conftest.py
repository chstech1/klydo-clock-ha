from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.klydo_clock.models import KlydoIdentity, KlydoState


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def client():
    with patch("custom_components.klydo_clock.KlydoClient", autospec=True) as factory:
        instance = factory.return_value
        instance.identify = AsyncMock(return_value=KlydoIdentity("stable-test-id"))
        instance.poll = AsyncMock(
            return_value=KlydoState(
                app_version="623.3",
                night_mode=False,
                night_mode_setting="OFF",
                app_running=True,
                app_foreground=True,
                free_storage_bytes=1024**3,
            )
        )
        yield instance


@pytest.fixture
def entry(hass):
    entry = MockConfigEntry(
        domain="klydo_clock",
        title="Klydo Clock",
        unique_id="stable-test-id",
        data={"host": "clock.example", "port": 1379},
    )
    entry.add_to_hass(hass)
    return entry
