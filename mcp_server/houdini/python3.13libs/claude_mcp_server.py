"""Runs inside Houdini: a localhost TCP server that executes commands from the Claude MCP bridge.

Protocol: one JSON object per line, {"command": str, "params": dict} -> {"ok": bool, "result"|"error": ...}.
Manual control from the Houdini Python shell:
    import claude_mcp_server; claude_mcp_server.start()   # or .stop()
"""
import contextlib
import io
import json
import os
import socket
import tempfile
import threading
import traceback

import hou

HOST = "127.0.0.1"
PORT = int(os.environ.get("CLAUDE_MCP_PORT", "9876"))

_server = None


def _node(path):
    n = hou.node(path)
    if n is None:
        raise ValueError("Node not found: %s" % path)
    return n


def _parm_value(p):
    try:
        return p.eval()
    except Exception:
        return p.unexpandedString()


def _node_summary(n):
    return {"path": n.path(), "type": n.type().name(), "category": n.type().category().name()}


# ---------------------------------------------------------------- commands

def cmd_ping(params):
    return {"houdini": hou.applicationVersionString(), "hip": hou.hipFile.path()}


def cmd_get_scene_info(params):
    root = params.get("root", "/")
    depth = int(params.get("depth", 2))

    def walk(n, d):
        info = _node_summary(n)
        if d > 0:
            kids = n.children()
            if kids:
                info["children"] = [walk(c, d - 1) for c in kids]
        return info

    return {
        "hip": hou.hipFile.path(),
        "frame": hou.frame(),
        "fps": hou.fps(),
        "frame_range": list(hou.playbar.frameRange()),
        "tree": walk(_node(root), depth),
    }


def cmd_get_node_info(params):
    n = _node(params["path"])
    info = _node_summary(n)
    info["inputs"] = [i.path() if i else None for i in n.inputs()]
    info["outputs"] = [o.path() for o in n.outputs()]
    info["children"] = [c.name() for c in n.children()]
    if params.get("include_parms", True):
        parms = {}
        for p in n.parms():
            if p.isAtDefault() and not params.get("all_parms", False):
                continue
            parms[p.name()] = _parm_value(p)
        info["parms"] = parms
    for flag in ("isDisplayFlagSet", "isRenderFlagSet", "isBypassed"):
        if hasattr(n, flag):
            info[flag] = getattr(n, flag)()
    errs = n.errors()
    if errs:
        info["errors"] = list(errs)
    warns = n.warnings()
    if warns:
        info["warnings"] = list(warns)
    geo = getattr(n, "geometry", None)
    if callable(geo):
        try:
            g = geo()
            if g is not None:
                info["geometry"] = {
                    "points": len(g.iterPoints()),
                    "prims": len(g.iterPrims()),
                    "point_attribs": [a.name() for a in g.pointAttribs()],
                    "prim_attribs": [a.name() for a in g.primAttribs()],
                    "bbox": [list(g.boundingBox().minvec()), list(g.boundingBox().maxvec())],
                }
        except Exception:
            pass
    return info


def cmd_create_node(params):
    parent = _node(params.get("parent", "/obj"))
    n = parent.createNode(params["type"], params.get("name"))
    if params.get("parms"):
        n.setParms(params["parms"])
    if params.get("input"):
        n.setInput(0, _node(params["input"]))
    n.moveToGoodPosition()
    if params.get("display", False) and hasattr(n, "setDisplayFlag"):
        n.setDisplayFlag(True)
        if hasattr(n, "setRenderFlag"):
            n.setRenderFlag(True)
    return _node_summary(n)


def cmd_set_parms(params):
    n = _node(params["path"])
    n.setParms(params["parms"])
    return {p: _parm_value(n.parm(p)) for p in params["parms"] if n.parm(p)}


def cmd_connect_nodes(params):
    dst = _node(params["to"])
    src = _node(params["from"]) if params.get("from") else None
    dst.setInput(int(params.get("input_index", 0)), src, int(params.get("output_index", 0)))
    return {"connected": [params.get("from"), params["to"]]}


def cmd_delete_node(params):
    _node(params["path"]).destroy()
    return {"deleted": params["path"]}


def cmd_execute_python(params):
    ns = {"hou": hou, "result": None}
    out = io.StringIO()
    with hou.undos.group("Claude MCP"), contextlib.redirect_stdout(out):
        exec(params["code"], ns)
    res = ns.get("result")
    try:
        json.dumps(res)
    except TypeError:
        res = repr(res)
    return {"stdout": out.getvalue(), "result": res}


def cmd_viewport_screenshot(params):
    sv = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
    if sv is None:
        raise RuntimeError("No Scene Viewer pane found")
    path = params.get("path") or os.path.join(tempfile.gettempdir(), "claude_houdini_viewport.png")
    f = hou.frame()
    s = sv.flipbookSettings().stash()
    s.frameRange((f, f))
    s.output(path.replace("\\", "/"))
    s.useResolution(True)
    s.resolution((int(params.get("width", 960)), int(params.get("height", 540))))
    sv.flipbook(sv.curViewport(), s)
    return {"path": path}


def cmd_save_hip(params):
    if params.get("path"):
        hou.hipFile.save(params["path"])
    else:
        hou.hipFile.save()
    return {"hip": hou.hipFile.path()}


COMMANDS = {k[4:]: v for k, v in globals().items() if k.startswith("cmd_")}


# ---------------------------------------------------------------- server

def _run_on_main(fn, params):
    if hou.isUIAvailable():
        import hdefereval
        return hdefereval.executeInMainThreadWithResult(fn, params)
    return fn(params)


def _handle(line):
    try:
        req = json.loads(line)
        fn = COMMANDS.get(req.get("command"))
        if fn is None:
            raise ValueError("Unknown command: %s" % req.get("command"))
        return {"ok": True, "result": _run_on_main(fn, req.get("params") or {})}
    except Exception as e:
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, e), "traceback": traceback.format_exc()}


def _client(conn):
    with conn, conn.makefile("rwb") as f:
        for line in f:
            if not line.strip():
                continue
            f.write((json.dumps(_handle(line.decode("utf-8")), default=str) + "\n").encode("utf-8"))
            f.flush()


class _Server(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True, name="ClaudeMCPServer")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((HOST, PORT))
        self.sock.listen(5)

    def run(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=_client, args=(conn,), daemon=True).start()


def start():
    global _server
    if _server is not None:
        return
    try:
        _server = _Server()
    except OSError as e:
        print("[Claude MCP] could not bind %s:%d (%s)" % (HOST, PORT, e))
        return
    _server.start()
    print("[Claude MCP] listening on %s:%d" % (HOST, PORT))


def stop():
    global _server
    if _server is not None:
        _server.sock.close()
        _server = None
        print("[Claude MCP] stopped")
