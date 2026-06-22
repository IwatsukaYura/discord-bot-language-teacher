"""lib.interaction_router のテスト。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from lib.interaction_router import InteractionRoute, route_component_interaction


def _make_interaction(response_done: bool = False) -> MagicMock:
    interaction = MagicMock()
    interaction.response.is_done = MagicMock(return_value=response_done)
    interaction.response.send_message = AsyncMock()
    return interaction


def _parse_quiz(custom_id: str) -> tuple | None:
    if not custom_id.startswith("quiz:"):
        return None
    _, a, b = custom_id.split(":")
    return int(a), int(b)


class TestRouteComponentInteraction:
    async def test_dispatches_to_matching_route_with_parsed_args(self):
        handler = AsyncMock()
        routes = (InteractionRoute("quiz", _parse_quiz, handler, "error"),)
        interaction = _make_interaction()

        handled = await route_component_interaction(interaction, "quiz:7:2", routes)

        assert handled is True
        handler.assert_awaited_once_with(interaction, 7, 2)

    async def test_returns_false_when_no_route_matches(self):
        handler = AsyncMock()
        routes = (InteractionRoute("quiz", _parse_quiz, handler, "error"),)
        interaction = _make_interaction()

        handled = await route_component_interaction(interaction, "unknown:1", routes)

        assert handled is False
        handler.assert_not_awaited()

    async def test_first_matching_route_wins(self):
        first = AsyncMock()
        second = AsyncMock()
        routes = (
            InteractionRoute("first", _parse_quiz, first, "error"),
            InteractionRoute("second", _parse_quiz, second, "error"),
        )
        interaction = _make_interaction()

        await route_component_interaction(interaction, "quiz:1:0", routes)

        first.assert_awaited_once()
        second.assert_not_awaited()

    async def test_handler_error_sends_route_error_message(self):
        handler = AsyncMock(side_effect=RuntimeError("boom"))
        routes = (InteractionRoute("quiz", _parse_quiz, handler, "やり直してね"),)
        interaction = _make_interaction(response_done=False)

        handled = await route_component_interaction(interaction, "quiz:1:0", routes)

        assert handled is True
        interaction.response.send_message.assert_awaited_once_with(
            "やり直してね", ephemeral=True,
        )

    async def test_handler_error_after_response_does_not_send_again(self):
        handler = AsyncMock(side_effect=RuntimeError("boom"))
        routes = (InteractionRoute("quiz", _parse_quiz, handler, "error"),)
        interaction = _make_interaction(response_done=True)

        await route_component_interaction(interaction, "quiz:1:0", routes)

        interaction.response.send_message.assert_not_awaited()

    async def test_routes_are_immutable(self):
        route = InteractionRoute("quiz", _parse_quiz, AsyncMock(), "error")
        with pytest.raises(AttributeError):
            route.name = "other"
