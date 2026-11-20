# Connect an agent to KITQUEN Forge

Install the Blender extension from the supplied ZIP. Open the **Forge** tab in the 3D View sidebar with **N**, switch to Object Mode, select the scene to use, and click **Start Connection**. **Copy Session Path** gives you the full path to the live `session.json`. The session is specific to this connection. Update the client's arguments after restarting the bridge or Blender.

From the extracted source directory, install the MCP package with `python -m pip install .`. If you use a virtual environment, supply its Python executable as an absolute path in the commands below.

## Codex

```sh
codex mcp add kitquen-forge -- python -m forge_mcp --session "/absolute/path/session.json"
codex mcp list
```

Start a new Codex session after registering the server. Copy the complete `skills/kitquen-forge` folder into your modeling project's `.agents/skills/` directory, then invoke `$kitquen-forge` or let Codex discover it. [Codex MCP](https://developers.openai.com/codex/mcp) · [Codex skills](https://developers.openai.com/codex/skills)

### Windows quick setup

After clicking **Copy Session Path** in Blender, open PowerShell and paste this block.

```powershell
$forgeSession = (Get-Clipboard -Raw).Trim().Trim('"')
if (-not (Test-Path -LiteralPath $forgeSession -PathType Leaf)) {
    throw 'In Blender, click Forge > Start Connection, then Copy Session Path.'
}
codex mcp add kitquen-forge -- (Get-Command python).Source -m forge_mcp --session $forgeSession
```

Open a new Codex chat and ask it to call `forge_status`. The MCP server is the connection to Blender. The optional skill is the instruction folder for modeling tasks.

## Claude Code

```sh
claude mcp add --transport stdio kitquen-forge -- python -m forge_mcp --session "/absolute/path/session.json"
claude mcp list
```

Run the command from your modeling project directory. Copy `skills/kitquen-forge` into `.claude/skills/` within that project. Invoke the skill with `/kitquen-forge`. [Claude Code MCP](https://code.claude.com/docs/en/mcp) · [Claude Code skills](https://code.claude.com/docs/en/skills)

On Windows, quote absolute paths such as `"C:\path\to\session.json"`. To update registration, remove the old entry with `codex mcp remove kitquen-forge` or `claude mcp remove kitquen-forge` and rerun the corresponding add command with the current path.

## First modeling request

Ask the agent to check `forge_status`, then execute the following in the approved scene and inspect `tile`.

```text
+cube/tile size=4,4,1
+hole/tile d=1
@color/tile #FF6600
```

Approve an export folder when you start the connection to allow export and rendering. Export filenames are relative to that folder and cannot overwrite existing files.
