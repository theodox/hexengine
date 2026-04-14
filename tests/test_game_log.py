"""Tests for :mod:`hexengine.game_log` and ``Message.try_from_json``."""

from __future__ import annotations

import asyncio
import json
import unittest

from hexengine.game_log import GameLogger, game_logger_scope, get_game_logger
from hexengine.gamedef.builtin import InterleavedTwoFactionGameDefinition
from hexengine.server import GameServer, Message
from hexengine.server.protocol import JoinGameRequest
from hexengine.state import GameState


class TestMessageTryFromJson(unittest.TestCase):
    def test_unknown_type_returns_none(self) -> None:
        raw = json.dumps({"type": "future_message", "payload": {}})
        self.assertIsNone(Message.try_from_json(raw))

    def test_known_type_round_trip(self) -> None:
        m = Message(type="error", payload={"error": "x"})
        got = Message.try_from_json(m.to_json())
        self.assertIsNotNone(got)
        assert got is not None
        self.assertEqual(got.type, "error")
        self.assertEqual(got.payload, {"error": "x"})

    def test_non_object_payload_becomes_empty_dict(self) -> None:
        raw = json.dumps({"type": "error", "payload": "bad"})
        got = Message.try_from_json(raw)
        self.assertIsNotNone(got)
        assert got is not None
        self.assertEqual(got.payload, {})


class TestGameLogger(unittest.TestCase):
    def test_enqueue_only_inside_scope(self) -> None:
        buf: list[tuple[str, str, str]] = []

        def capture(level: str, name: str, text: str) -> None:
            buf.append((level, name, text))

        gl = GameLogger(logger_name="t.game", enqueue_client=capture)
        with game_logger_scope(gl):
            get_game_logger().info("a %s", "b")
        self.assertEqual(buf, [("INFO", "t.game", "a b")])

    def test_fallback_has_no_enqueue(self) -> None:
        buf: list[tuple[str, str, str]] = []
        _ = buf
        get_game_logger().info("offline")
        self.assertEqual(buf, [])


class TestGameServerGameLog(unittest.TestCase):
    def test_flush_queue_broadcasts_server_log(self) -> None:
        async def run() -> None:
            gd = InterleavedTwoFactionGameDefinition()
            gs = GameServer(GameState.create_empty(), game_definition=gd)
            received: list[Message] = []

            def h(_pid: str, msg: Message) -> None:
                received.append(msg)

            gs.add_message_handler(h)
            await gs.handle_message(
                "p1",
                JoinGameRequest(player_name="A", faction="Red").to_message(),
            )
            gs._pending_game_log_events.append(("INFO", "x.y", "hello"))
            await gs._flush_game_log_queue()

            logs = [m for m in received if m.type == "server_log"]
            self.assertEqual(len(logs), 1)
            self.assertEqual(
                logs[0].payload,
                {"level": "INFO", "logger": "x.y", "message": "hello"},
            )

        asyncio.run(run())

    def test_manual_scope_flush(self) -> None:
        async def run() -> None:
            gd = InterleavedTwoFactionGameDefinition()
            gs = GameServer(GameState.create_empty(), game_definition=gd)
            received: list[Message] = []

            def h(_pid: str, msg: Message) -> None:
                received.append(msg)

            gs.add_message_handler(h)
            await gs.handle_message(
                "p1",
                JoinGameRequest(player_name="A", faction="Red").to_message(),
            )
            gl = gs._make_game_logger()
            with game_logger_scope(gl):
                get_game_logger().info("during")
            await gs._flush_game_log_queue()

            logs = [m for m in received if m.type == "server_log"]
            self.assertEqual(len(logs), 1)
            self.assertEqual(logs[0].payload["message"], "during")

        asyncio.run(run())
