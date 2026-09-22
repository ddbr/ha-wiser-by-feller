"""Platform for number integration: per-device tilt steps for venetian blinds."""

from __future__ import annotations

from aiowiserbyfeller import Device, Load, Motor
from aiowiserbyfeller.const import KIND_VENETIAN_BLINDS
from homeassistant.components.number import NumberMode, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import WiserCoordinator
from .entity import WiserEntity
from .util import DEFAULT_TILT_STEPS, MAX_TILT_STEPS, set_tilt_steps

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Wiser number entities."""
    coordinator: WiserCoordinator = entry.runtime_data

    assert coordinator.loads is not None
    assert coordinator.devices is not None
    assert coordinator.rooms is not None
    entities: list[WiserEntity] = []
    for load in coordinator.loads.values():
        # Same condition as the tiltable cover entity in cover.py.
        if (
            not isinstance(load, Motor)
            or load.sub_type == "relay"
            or load.kind != KIND_VENETIAN_BLINDS
        ):
            continue

        device = coordinator.devices[load.device]
        room = coordinator.rooms[load.room] if load.room is not None else None
        entities.append(WiserTiltStepsEntity(coordinator, load, device, room))

    if entities:
        async_add_entities(entities)


class WiserTiltStepsEntity(WiserEntity, RestoreNumber):
    """Number of Wiser tilt steps Home Assistant uses for a full tilt.

    The µGateway knows tilt steps 0..9. Moving to a tilt target runs the motor
    continuously, which turns the slats further than the same number of short
    button presses. Reducing the steps used for "tilt open / 100 %" compensates
    for that. The value is stored in Home Assistant only.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 1
    _attr_native_max_value = MAX_TILT_STEPS
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:blinds-horizontal"

    def __init__(
        self,
        coordinator: WiserCoordinator,
        load: Load,
        device: Device,
        room: dict | None,
    ) -> None:
        """Set up the tilt steps entity."""
        super().__init__(coordinator, load, device, room)
        self._attr_unique_id = f"{self._attr_raw_unique_id}_tilt_steps"
        self._attr_name = "Kippschritte"
        self._attr_native_value = DEFAULT_TILT_STEPS

    async def async_added_to_hass(self) -> None:
        """Restore the last value and publish it to the cover entity."""
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last is not None and last.native_value is not None:
            self._attr_native_value = last.native_value
        self._attr_native_value = set_tilt_steps(
            self.raw_unique_id, self._attr_native_value
        )
        self.async_write_ha_state()
        # Let the cover entity re-evaluate its tilt position.
        self.coordinator.async_update_listeners()

    async def async_set_native_value(self, value: float) -> None:
        """Change the number of tilt steps."""
        self._attr_native_value = set_tilt_steps(self.raw_unique_id, value)
        self.async_write_ha_state()
        self.coordinator.async_update_listeners()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Ignore gateway updates; the value is stored in Home Assistant only."""
