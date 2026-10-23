"""Tests for the stdio MCP server. Runs without Houdini: the socket bridge is mocked or unreachable."""
import io
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import houdini_mcp_server as server


def run_main(lines):
    """Feed raw stdin lines to main() and return the parsed JSON replies."""
    stdin = io.TextIOWrapper(io.BytesIO("".join(lines).encode("utf-8")))
    stdout = io.TextIOWrapper(io.BytesIO())
    with mock.patch.object(sys, "stdin", stdin), mock.patch.object(sys, "stdout", stdout):
        server.main()
    return [json.loads(line) for line in stdout.buffer.getvalue().decode("utf-8").splitlines()]


class HandleTests(unittest.TestCase):
    def test_initialize_echoes_protocol_version(self):
        result = server.handle({"method": "initialize", "params": {"protocolVersion": "2024-11-05"}})
        self.assertEqual(result["protocolVersion"], "2024-11-05")
        self.assertEqual(result["serverInfo"]["name"], "houdini")

    def test_tools_list_names_are_unique(self):
        names = [t["name"] for t in server.handle({"method": "tools/list"})["tools"]]
        self.assertIn("ping", names)
        self.assertEqual(len(names), len(set(names)))

    def test_unknown_method_raises_key_error(self):
        with self.assertRaises(KeyError):
            server.handle({"method": "nope"})


class ToolCallTests(unittest.TestCase):
    def test_success_returns_json_text(self):
        with mock.patch.object(server, "call_houdini", return_value={"ok": True, "result": {"version": "22.0"}}):
            resp = server.tool_call("ping", {})
        self.assertNotIn("isError", resp)
        self.assertEqual(json.loads(resp["content"][0]["text"]), {"version": "22.0"})

    def test_error_includes_traceback(self):
        reply = {"ok": False, "error": "boom", "traceback": "Traceback..."}
        with mock.patch.object(server, "call_houdini", return_value=reply):
            resp = server.tool_call("ping", {})
        self.assertTrue(resp["isError"])
        self.assertIn("boom", resp["content"][0]["text"])
        self.assertIn("Traceback...", resp["content"][0]["text"])

    def test_unreachable_houdini_reports_error(self):
        with mock.patch.object(server.socket, "create_connection", side_effect=ConnectionRefusedError()):
            resp = server.call_houdini("ping", {})
        self.assertFalse(resp["ok"])
        self.assertIn("Cannot reach Houdini", resp["error"])


class MainLoopTests(unittest.TestCase):
    def test_malformed_json_returns_parse_error_and_keeps_running(self):
        replies = run_main([
            "{not json\n",
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}) + "\n",
        ])
        self.assertEqual(replies[0]["error"]["code"], -32700)
        self.assertIsNone(replies[0]["id"])
        self.assertEqual(replies[1], {"jsonrpc": "2.0", "id": 1, "result": {}})

    def test_notifications_and_blank_lines_get_no_reply(self):
        replies = run_main(["\n", json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"])
        self.assertEqual(replies, [])

    def test_unknown_method_returns_method_not_found(self):
        replies = run_main([json.dumps({"jsonrpc": "2.0", "id": 7, "method": "nope"}) + "\n"])
        self.assertEqual(replies[0]["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main()
