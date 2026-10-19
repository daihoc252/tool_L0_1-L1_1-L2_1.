"""Markdown report: what the script does, how each variable was named, and
the de-obfuscated code in a ```lua block."""

KIND_LABELS = {
    "local": "local",
    "param": "parameter",
    "for": "loop variable",
    "localfunc": "local function",
    "global": "global",
}


def describe_purpose(summary):
    """A few plain-English sentences describing the script."""
    s = summary
    side = {"client": "a **client-side**", "server": "a **server-side**"}.get(s.side, "a **shared**")
    framework = " built on **%s**" % " + ".join(s.frameworks) if s.frameworks else ""
    sentences = ["This looks like %s FiveM script%s." % (side, framework)]

    def quoted(items):
        return ", ".join("`%s`" % i for i in items if i is not None)

    if s.events_handled:
        sentences.append("It reacts to the events %s." % quoted(s.events_handled))
    if s.events_triggered_server:
        sentences.append("It sends %s to the server." % quoted(s.events_triggered_server))
    if s.events_triggered_client:
        sentences.append("It sends %s to clients." % quoted(s.events_triggered_client))
    if s.events_triggered_local:
        sentences.append("It triggers the local events %s." % quoted(s.events_triggered_local))
    if s.commands:
        sentences.append("It registers the chat command(s) %s." % ", ".join("`/%s`" % c for c in s.commands if c))
    if s.callbacks_registered:
        sentences.append("It provides the server callbacks %s." % quoted(s.callbacks_registered))
    if s.callbacks_called:
        sentences.append("It requests the server callbacks %s." % quoted(s.callbacks_called))
    if s.nui_callbacks:
        sentences.append("It talks to an HTML (NUI) interface through %s." % quoted(s.nui_callbacks))
    if s.exports:
        sentences.append("It exports %s to other resources." % quoted(s.exports))
    if s.usable_items:
        sentences.append("It makes the items %s usable." % quoted(s.usable_items))
    if s.threads:
        sentences.append("It starts %d thread(s) (game loops that run continuously)." % s.threads)
    if s.globals_defined:
        sentences.append("It defines the global function(s) %s." % quoted(s.globals_defined))
    plumbing = {"AddEventHandler", "RegisterNetEvent", "RegisterServerEvent", "TriggerEvent",
                "TriggerServerEvent", "TriggerClientEvent", "RegisterCommand", "CreateThread",
                "Wait", "SetTimeout", "RegisterNUICallback", "RegisterKeyMapping"}
    natives = sorted(((n, c) for n, c in s.natives.items() if n not in plumbing and n not in s.globals_defined),
                     key=lambda kv: (-kv[1], kv[0]))[:10]
    if natives:
        sentences.append("Main game natives used: %s." % ", ".join("`%s`" % n for n, _ in natives))
    return " ".join(sentences)


METHOD_NOTES = """\
* **Decompiled code reuses variables.** Tools such as *unluac* emit one local
  per VM register (`L0_1`, `A0_2`, ...: `L` = local, `A` = argument, the
  suffix is the function nesting depth) and reuse it for unrelated values.
  A reaching-definitions analysis splits each such variable into independent
  *values* (def-use webs) so every value gets its own name. Once a closure
  (event handler, thread...) can see a variable, all later accesses stay
  one shared variable; in functions using `goto` variables are only
  renamed, never split.
* **Names come from evidence.** Each value collects weighted hints: what
  produced it (`GetEntityCoords(...)` gives `coords`, `"esx:setJob"` passed to
  `AddEventHandler` gives `eventName`, a function registered for that event
  gives `onSetJob`), how it is used (passed as the `entity` argument of a
  native, `:getMoney()` called on it gives `xPlayer`), where it is stored
  (`DrawText3D = L3_1` gives `drawText3D`) and FiveM knowledge (parameters of
  `playerDropped`, `RegisterCommand` handlers, ESX/QBCore callbacks...). The
  strongest hint wins; the "Why" column below quotes it.
* **Renaming is scope-safe.** A new name never equals a global or a
  meaningful local, and two variables share a name only if neither is used
  inside the other's scope. Logic, control flow and every call are unchanged.
"""


def build_report(result, title="script"):
    lines = ["# De-obfuscation report: `%s`" % title, ""]
    lines += ["## What the script does", "", describe_purpose(result.summary), ""]
    lines += ["## How names were inferred", "", METHOD_NOTES]
    lines += ["## Renamed variables", ""]
    if result.renames:
        lines += ["| Line | Original | New name | Kind | Why |", "|---:|---|---|---|---|"]
        for r in result.renames:
            lines.append("| %d | `%s` | `%s` | %s | %s |" % (
                r.line, r.old, r.new, KIND_LABELS.get(r.kind, r.kind), r.reason.replace("|", "\\|")))
    else:
        lines.append("No obfuscated variables matched the pattern.")
    lines.append("")
    if result.skipped_globals:
        lines += ["Obfuscated-looking **globals** were left unchanged (use `--rename-globals` "
                  "to rename them): " + ", ".join("`%s`" % g for g in sorted(result.skipped_globals)), ""]
    lines += ["## Verification", ""]
    v = result.verification
    if v is None:
        lines.append("Verification was skipped.")
    elif v.ok:
        lines.append("Passed: the output has the same structure as the original, and each of "
                     "the %d local-variable reads sees exactly the same definitions as before."
                     % v.uses_checked)
        if v.lua_checked:
            lines.append("The output also compiles with Lua 5.4.")
    else:
        lines.append("**FAILED** - please report this as a bug:")
        lines += ["* " + p for p in v.problems]
        if v.lua_error:
            lines.append("* Lua 5.4 rejected the output: %s" % v.lua_error)
    lines += ["", "## De-obfuscated code", "", "```lua", result.code.rstrip("\n"), "```", ""]
    return "\n".join(lines)
