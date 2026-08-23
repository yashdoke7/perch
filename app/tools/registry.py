"""The tool surface (architecture Part VI).

Policy, enforced here rather than documented and hoped for:

    1. READ IS FREE, WRITE ASKS. Anything that changes state outside PERCH --
       or runs arbitrary code -- is marked confirm=True, and dispatch() will
       not run it without an approval callback that returns True. The default
       is REFUSAL: a caller that passes no callback cannot invoke a confirming
       tool at all.
    2. EVERY CALL IS LOGGED and shown in the panel.
    3. PRIVATE MODE REMOVES THE NETWORK TOOLS. A privacy guarantee that leaks
       through a search query is not a guarantee -- so web_search and web_fetch
       are not merely refused at call time, they are never declared.

Rule 1 was documented here for some time while dispatch() ignored the flag
entirely, which meant a model could overwrite any file under the user's home
directory, or write memory silently, with no prompt -- directly contradicting
architecture Part VI and the "nothing is stored silently from ordinary chat"
rule in §3.4. Deny-by-default is the fix, and it is enforced in ONE place so
that a new tool marked confirm=True is gated without touching either tool loop.
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .. import config


@dataclass
class Tool:
    name: str
    description: str
    params: dict
    fn: Callable[..., str]
    network: bool = False
    confirm: bool = False


TOOLS: dict[str, Tool] = {}


def tool(name: str, description: str, params: dict, network: bool = False,
         confirm: bool = False):
    def wrap(fn):
        TOOLS[name] = Tool(name, description, params, fn, network, confirm)
        return fn
    return wrap


def _s(desc: str) -> dict:
    return {"type": "string", "description": desc}


# ------------------------------------------------------------------ knowledge

@tool("web_search", "Search the web. Use when the answer depends on anything "
      "recent, or on facts you are not certain of.",
      {"query": _s("the search query")}, network=True)
def web_search(query: str = "") -> str:
    url = "https://duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", "ignore")
    except Exception as exc:
        return f"search failed: {exc}"

    import re
    hits = re.findall(r'result__a"[^>]*>(.*?)</a>.*?result__snippet"[^>]*>(.*?)</a>',
                      html, re.S)[:6]
    if not hits:
        return "no results parsed"
    clean = re.compile(r"<[^>]+>")
    return "\n\n".join(
        f"{clean.sub('', t).strip()}\n{clean.sub('', s).strip()[:280]}" for t, s in hits
    )


@tool("web_fetch", "Fetch a URL and return its readable text.",
      {"url": _s("the absolute URL")}, network=True)
def web_fetch(url: str = "") -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=25) as resp:
            html = resp.read().decode("utf-8", "ignore")
    except Exception as exc:
        return f"fetch failed: {exc}"
    import re
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()[:6000]


# ----------------------------------------------------------------------- files

def _allowed(path: Path) -> bool:
    """Scoped to user-declared roots. Home and the PERCH dir, nothing else."""
    try:
        resolved = path.resolve()
    except OSError:
        return False
    roots = [Path.home().resolve(), config.ROOT.resolve()]
    return any(str(resolved).startswith(str(r)) for r in roots)


@tool("file_read", "Read a text file from disk.", {"path": _s("absolute path")})
def file_read(path: str = "") -> str:
    p = Path(path)
    if not _allowed(p):
        return "refused: outside the allowed roots"
    if not p.is_file():
        return "not a file"
    try:
        return p.read_text(encoding="utf-8", errors="replace")[:8000]
    except OSError as exc:
        return f"read failed: {exc}"


@tool("dir_list", "List the entries of a directory.", {"path": _s("absolute path")})
def dir_list(path: str = "") -> str:
    p = Path(path)
    if not _allowed(p) or not p.is_dir():
        return "refused or not a directory"
    return "\n".join(sorted(x.name + ("/" if x.is_dir() else "") for x in p.iterdir())[:200])


@tool("file_write", "Write text to a file. Overwrites.",
      {"path": _s("absolute path"), "content": _s("full file contents")}, confirm=True)
def file_write(path: str = "", content: str = "") -> str:
    p = Path(path)
    if not _allowed(p):
        return "refused: outside the allowed roots"
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"wrote {len(content)} chars to {p}"
    except OSError as exc:
        return f"write failed: {exc}"


# ------------------------------------------------------------------- documents

@tool("doc_parse", "Extract text from a PDF, DOCX or PPTX file.",
      {"path": _s("absolute path to the document")})
def doc_parse(path: str = "") -> str:
    p = Path(path)
    if not _allowed(p) or not p.is_file():
        return "refused or missing"
    suffix = p.suffix.lower()
    try:
        if suffix == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(str(p))
            return "\n".join((pg.extract_text() or "") for pg in reader.pages[:30])[:8000]
        if suffix == ".docx":
            import docx
            return "\n".join(par.text for par in docx.Document(str(p)).paragraphs)[:8000]
        if suffix == ".pptx":
            from pptx import Presentation
            prs = Presentation(str(p))
            return "\n".join(sh.text_frame.text for s in prs.slides
                             for sh in s.shapes if sh.has_text_frame)[:8000]
    except ImportError as exc:
        return f"parser not installed: {exc}"
    except Exception as exc:
        return f"parse failed: {exc}"
    return p.read_text(encoding="utf-8", errors="replace")[:8000]


# --------------------------------------------------------------------- compute

@tool("run_python", "Run a short Python snippet for arithmetic, dates or data "
      "munging. Print the result. The user is asked before it runs.",
      {"code": _s("python source; use print() for output")}, confirm=True)
def run_python(code: str = "") -> str:
    """Run a snippet in a separate interpreter.

    ⚠️ THIS IS NOT A SANDBOX, and calling it one would be the dangerous kind
    of wrong. `-I` gives isolated mode: it ignores PYTHONPATH, PYTHON* env
    vars and the user site directory, so the snippet cannot be hijacked by
    the environment. That is all it does. The snippet still runs with this
    process's full privileges -- it can read and write any file the user can,
    open sockets, and start other programs. The 10s timeout bounds how long
    it does so, not what it is allowed to do.

    Two consequences, both deliberate:

      * confirm=True, so it cannot run without the user approving THIS
        snippet. That is the real containment, and it is the same mechanism
        file_write uses.
      * it is a normal (non-network) tool, so it is still declared in private
        mode. A snippet that opens a socket would defeat that -- which is
        precisely why a human reads the code before it runs.

    A genuine sandbox (subprocess with dropped privileges, no network
    namespace, a read-only filesystem view) is the right fix and is not
    something to fake with a flag.
    """
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-c", code],
            capture_output=True, text=True, timeout=10,
        )
    except subprocess.TimeoutExpired:
        return "timed out after 10s"
    out = (proc.stdout or "") + (proc.stderr or "")
    return out.strip()[:3000] or "(no output)"


# ---------------------------------------------------------------------- memory

_store = None


def bind_memory(store) -> None:
    """The pipeline injects the live store so memory_* become real tools."""
    global _store
    _store = store


@tool("memory_search", "Search the user's own stored memory. Use when you need "
      "personal context that was not already supplied.",
      {"query": _s("what to look for"), "cls": _s("optional class: identity, "
       "project, academic, career, health, personal")})
def memory_search(query: str = "", cls: str = "") -> str:
    if _store is None:
        return "memory unavailable"
    from ..memory import classes as mc, embed
    from ..core import ranker, admission
    eligible = [cls] if cls in mc.CLASSES else list(mc.ORDER)
    cands = _store.candidates(eligible, embed.embed(query), 10)
    ranked = ranker.rank(cands, query)
    # The gate applies here too -- a tool call is not a way around it.
    result = admission.admit(ranked)
    if not result.admitted:
        return "nothing in memory cleared the relevance floor for that query."
    return "\n\n".join(s.item.rendered() for s in result.admitted[:5])


@tool("memory_write", "Store a fact about the user in their memory.",
      {"cls": _s("identity, project, academic, career, health or personal"),
       "title": _s("short title"), "body": _s("the fact"),
       "tags": _s("comma-separated tags")}, confirm=True)
def memory_write(cls: str = "", title: str = "", body: str = "", tags: str = "") -> str:
    if _store is None:
        return "memory unavailable"
    from ..memory import classes as mc
    from ..memory.schema import MemoryItem
    if cls not in mc.CLASSES:
        return f"unknown class {cls!r}; valid: {', '.join(mc.ORDER)}"
    item = MemoryItem(cls=cls, title=title, body=body,
                      tags=[t.strip() for t in tags.split(",") if t.strip()],
                      source_kind="live")
    stored, how = _store.add(item)
    return f"{how} {stored.id}"


# -------------------------------------------------------------------- dispatch

def schemas(allow_network: bool = True) -> list[dict]:
    out = []
    for t in TOOLS.values():
        if t.network and not allow_network:
            continue      # never DECLARED in private mode, not merely refused
        out.append({
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": {
                    "type": "object",
                    "properties": t.params,
                    "required": list(t.params.keys())[:1],
                },
            },
        })
    return out


def describe_call(name: str, args: dict) -> str:
    """One human-readable line: what this call will actually do.

    Shown in the confirmation prompt, so the user approves a specific action
    rather than an abstract tool name. Values are truncated because a
    file_write body can be arbitrarily long and the dialog is small.
    """
    t = TOOLS.get(name)
    if t is None:
        return f"unknown tool {name!r}"
    shown = []
    for k, v in args.items():
        text = str(v).replace("\n", " ")
        shown.append(f"{k}={text[:120]}{'…' if len(text) > 120 else ''}")
    return f"{name}({', '.join(shown)})"


def dispatch(name: str, args: dict, allow_network: bool = True,
             on_confirm: Callable[[str, dict], bool] | None = None) -> str:
    """Run a tool, subject to the three policy rules above.

    on_confirm(name, args) -> bool is how a UI grants permission for a
    confirming tool. It is deliberately NOT optional-with-a-default-of-yes:
    if a confirming tool is reached with no callback, the call is refused.
    A headless caller (tests, `python -m app ask`) therefore gets read-only
    tools unless it opts in explicitly, which is the safe direction to fail.
    """
    t = TOOLS.get(name)
    if t is None:
        return f"unknown tool {name!r}"
    if t.network and not allow_network:
        return "refused: private mode - network tools are disabled"

    if t.confirm:
        if on_confirm is None:
            return (f"refused: {name} changes state outside PERCH and needs "
                    "confirmation, but nothing is available to ask")
        try:
            approved = bool(on_confirm(name, dict(args)))
        except Exception as exc:                          # noqa: BLE001
            # A broken or closed UI must read as "no", never as "yes".
            return f"refused: could not ask for confirmation ({exc})"
        if not approved:
            return f"refused: the user declined {name}"

    try:
        return t.fn(**args)
    except TypeError as exc:
        return f"bad arguments: {exc}"
    except Exception as exc:
        return f"tool error: {exc}"


def names(allow_network: bool = True) -> list[str]:
    return [t.name for t in TOOLS.values() if allow_network or not t.network]
