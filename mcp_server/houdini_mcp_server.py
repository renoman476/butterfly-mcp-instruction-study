"""MCP server (stdio, stdlib only) that forwards tool calls to the Claude bridge running inside Houdini."""
import base64
import json
import os
import socket
import sys

HOST = "127.0.0.1"
PORT = int(os.environ.get("CLAUDE_MCP_PORT", "9876"))

TOOLS = [
    {
        "name": "ping",
        "description": "Check the connection to Houdini; returns the Houdini version and current .hip path.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_scene_info",
        "description": "Return the node tree under a root (default '/') plus frame/fps/frame range.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string", "description": "Root node path, e.g. '/obj'"},
                "depth": {"type": "integer", "description": "Recursion depth (default 2)"},
            },
        },
    },
    {
        "name": "get_node_info",
        "description": "Inspect a node: type, connections, non-default parms, flags, errors, geometry summary.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "include_parms": {"type": "boolean"},
                "all_parms": {"type": "boolean", "description": "Include parms at default values too"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "create_node",
        "description": "Create a node, e.g. parent='/obj' type='geo', or parent='/obj/geo1' type='box'.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "parent": {"type": "string"},
                "type": {"type": "string"},
                "name": {"type": "string"},
                "parms": {"type": "object", "description": "Parm name -> value (tuples as e.g. 'tx','ty' or 't': [x,y,z])"},
                "input": {"type": "string", "description": "Path of node to wire into input 0"},
                "display": {"type": "boolean", "description": "Set display/render flag"},
            },
            "required": ["parent", "type"],
        },
    },
    {
        "name": "set_parms",
        "description": "Set parameters on a node.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "parms": {"type": "object"}},
            "required": ["path", "parms"],
        },
    },
    {
        "name": "connect_nodes",
        "description": "Wire node 'from' into input 'input_index' of node 'to'. Omit 'from' to disconnect.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "from": {"type": "string"},
                "to": {"type": "string"},
                "input_index": {"type": "integer"},
                "output_index": {"type": "integer"},
            },
            "required": ["to"],
        },
    },
    {
        "name": "delete_node",
        "description": "Delete a node.",
        "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    },
    {
        "name": "execute_python",
        "description": "Run Python inside Houdini (main thread, one undo group). 'hou' is pre-imported. "
        "Assign to `result` to return a value; print() output is returned as stdout.",
        "inputSchema": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]},
    },
    {
        "name": "viewport_screenshot",
        "description": "Flipbook the current frame of the Scene Viewer and return it as an image.",
        "inputSchema": {
            "type": "object",
            "properties": {"width": {"type": "integer"}, "height": {"type": "integer"}},
        },
    },
    {
        "name": "save_hip",
        "description": "Save the current .hip file, optionally to a new path.",
        "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}},
    },
]


def call_houdini(command, params):
    try:
        with socket.create_connection((HOST, PORT), timeout=300) as s, s.makefile("rwb") as f:
            f.write((json.dumps({"command": command, "params": params}) + "\n").encode("utf-8"))
            f.flush()
            line = f.readline()
    except OSError as e:
        return {"ok": False, "error": "Cannot reach Houdini on %s:%d (%s). Is Houdini open with the "
                "Claude MCP package loaded?" % (HOST, PORT, e)}
    if not line:
        return {"ok": False, "error": "Houdini closed the connection without a reply"}
    return json.loads(line.decode("utf-8"))


def tool_call(name, args):
    resp = call_houdini(name, args)
    if not resp.get("ok"):
        text = resp.get("error", "unknown error")
        if resp.get("traceback"):
            text += "\n\n" + resp["traceback"]
        return {"content": [{"type": "text", "text": text}], "isError": True}
    result = resp["result"]
    content = [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False, default=str)}]
    if name == "viewport_screenshot":
        try:
            with open(result["path"], "rb") as img:
                data = base64.b64encode(img.read()).decode("ascii")
            content.insert(0, {"type": "image", "data": data, "mimeType": "image/png"})
        except OSError as e:
            content.append({"type": "text", "text": "Could not read screenshot: %s" % e})
    return {"content": content}


def handle(msg):
    method = msg.get("method")
    if method == "initialize":
        return {
            "protocolVersion": msg.get("params", {}).get("protocolVersion", "2025-06-18"),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "houdini", "version": "1.0.0"},
        }
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        p = msg.get("params", {})
        return tool_call(p.get("name"), p.get("arguments") or {})
    if method == "ping":
        return {}
    raise KeyError(method)


def main():
    stdin = sys.stdin.buffer
    stdout = sys.stdout.buffer
    for raw in stdin:
        if not raw.strip():
            continue
        try:
            msg = json.loads(raw)
        except ValueError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
            stdout.write((json.dumps(reply) + "\n").encode("utf-8"))
            stdout.flush()
            continue
        if "id" not in msg:  # notification
            continue
        try:
            reply = {"jsonrpc": "2.0", "id": msg["id"], "result": handle(msg)}
        except KeyError:
            reply = {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": "Method not found"}}
        except Exception as e:
            reply = {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32603, "message": str(e)}}
        stdout.write((json.dumps(reply) + "\n").encode("utf-8"))
        stdout.flush()


if __name__ == "__main__":
    main()
