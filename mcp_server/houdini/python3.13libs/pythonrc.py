# Auto-start the Claude MCP bridge in interactive Houdini sessions only (not hython/batch renders).
import hou

if hou.isUIAvailable():
    import claude_mcp_server
    claude_mcp_server.start()
