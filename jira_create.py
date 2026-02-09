#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
import subprocess
import time
from typing import Any, Dict, List, Optional

import requests

LOG_PATH = "/tmp/jira_create_runtime.log"
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "ulauncher-jira-create")
os.makedirs(CACHE_DIR, exist_ok=True)


def log(msg: str) -> None:
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass


# ----------------------------
# Preferences / Environment
# ----------------------------
def _read_prefs() -> Dict[str, str]:
    base_url = (os.environ.get("JIRA_BASE_URL") or "").rstrip("/")
    email = os.environ.get("JIRA_EMAIL") or ""
    api_token = os.environ.get("JIRA_API_TOKEN") or ""
    default_project_key = (os.environ.get("JIRA_DEFAULT_PROJECT_KEY") or "").strip().upper()

    if base_url and email and api_token:
        return {
            "base_url": base_url,
            "email": email,
            "api_token": api_token,
            "default_project_key": default_project_key,
        }

    def get(pref_id: str) -> str:
        return os.environ.get(f"ULAUNCHER_EXTENSION_{pref_id.upper()}", "")

    return {
        "base_url": get("base_url").rstrip("/"),
        "email": get("email"),
        "api_token": get("api_token"),
        "default_project_key": get("default_project_key").strip().upper(),
    }


# ----------------------------
# Cache
# ----------------------------
def _cache_path(name: str) -> str:
    return os.path.join(CACHE_DIR, name)


def _load_cache(name: str, max_age_seconds: int) -> Optional[Any]:
    path = _cache_path(name)
    if not os.path.exists(path):
        return None

    try:
        st = os.stat(path)
        if time.time() - st.st_mtime > max_age_seconds:
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _save_cache(name: str, data: Any) -> None:
    path = _cache_path(name)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ----------------------------
# OS helpers
# ----------------------------
def _notify(title: str, body: str) -> None:
    subprocess.run(["notify-send", title, body], check=False)


def _wl_copy(text: str) -> None:
    subprocess.run(["wl-copy"], input=text.encode("utf-8"), check=False)


def _open_url(url: str) -> None:
    subprocess.run(["xdg-open", url], check=False)


def show_error_dialog(title: str, text: str) -> None:
    try:
        obj = json.loads(text)
        text = json.dumps(obj, indent=2, ensure_ascii=False)
    except Exception:
        pass

    subprocess.run(
        [
            "yad",
            "--title",
            title,
            "--width",
            "800",
            "--height",
            "500",
            "--center",
            "--text-info",
            "--wrap",
            "--editable",
            "--button=Close:0",
        ],
        input=text,
        text=True,
    )


# ----------------------------
# Jira HTTP
# ----------------------------
def _jira_headers(email: str, api_token: str) -> Dict[str, str]:
    basic = base64.b64encode(f"{email}:{api_token}".encode("utf-8")).decode("utf-8")
    return {
        "Authorization": f"Basic {basic}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _jira_get(
    base_url: str,
    headers: Dict[str, str],
    path: str,
    params: Optional[Dict[str, str]] = None,
) -> Any:
    url = f"{base_url}{path}"
    r = requests.get(url, headers=headers, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def _jira_post(base_url: str, headers: Dict[str, str], path: str, payload: Any) -> Any:
    url = f"{base_url}{path}"
    r = requests.post(url, headers=headers, json=payload, timeout=25)
    r.raise_for_status()
    return r.json()


# ----------------------------
# Jira payload helpers
# ----------------------------
def _adf_from_text(text: str) -> Dict[str, Any]:
    lines = text.splitlines() if text else []
    content: List[Dict[str, Any]] = []

    if not lines:
        content.append({"type": "paragraph", "content": [{"type": "text", "text": ""}]})
    else:
        for line in lines:
            content.append({"type": "paragraph", "content": [{"type": "text", "text": line}]})

    return {"type": "doc", "version": 1, "content": content}


# ----------------------------
# Jira data fetch
# ----------------------------
def _get_projects(base_url: str, headers: Dict[str, str]) -> List[Dict[str, str]]:
    cache = _load_cache("projects.json", max_age_seconds=24 * 3600)
    if cache:
        return cache

    start_at = 0
    max_results = 50
    out: List[Dict[str, str]] = []

    while True:
        data = _jira_get(
            base_url,
            headers,
            "/rest/api/3/project/search",
            params={"startAt": str(start_at), "maxResults": str(max_results)},
        )
        values = data.get("values", [])
        for p in values:
            key = p.get("key", "")
            name = p.get("name", "")
            if key:
                out.append({"key": key, "name": name})

        if data.get("isLast", True) or not values:
            break
        start_at += max_results

    out.sort(key=lambda x: (x["key"], x["name"]))
    _save_cache("projects.json", out)
    return out


def _get_createmeta_issue_types(
    base_url: str, headers: Dict[str, str], project_key: str
) -> List[Dict[str, str]]:
    cache_name = f"issuetypes_{project_key}.json"
    cache = _load_cache(cache_name, max_age_seconds=24 * 3600)
    if cache:
        return cache

    data = _jira_get(
        base_url,
        headers,
        "/rest/api/3/issue/createmeta",
        params={"projectKeys": project_key, "expand": "projects.issuetypes"},
    )
    projects = data.get("projects", [])
    if not projects:
        return []

    issuetypes = projects[0].get("issuetypes", [])
    out = [{"id": it.get("id", ""), "name": it.get("name", "")} for it in issuetypes if it.get("id")]
    out.sort(key=lambda x: x["name"])
    _save_cache(cache_name, out)
    return out


def _get_epics(base_url: str, headers: Dict[str, str], project_key: str) -> List[Dict[str, str]]:
    cache_name = f"epics_{project_key}.json"
    cache = _load_cache(cache_name, max_age_seconds=10 * 60)
    if cache:
        return cache

    jql = f'project = "{project_key}" AND issuetype = Epic ORDER BY updated DESC'
    data = _jira_get(
        base_url,
        headers,
        "/rest/api/3/search/jql",
        params={"jql": jql, "maxResults": "50", "fields": "summary,key"},
    )

    issues = data.get("issues", [])
    out = [
        {
            "key": i.get("key", ""),
            "summary": (i.get("fields", {}) or {}).get("summary", ""),
        }
        for i in issues
        if i.get("key")
    ]
    _save_cache(cache_name, out)
    return out


def _get_assignees(base_url: str, headers: Dict[str, str], project_key: str) -> List[Dict[str, str]]:
    cache_name = f"assignees_{project_key}.json"
    cache = _load_cache(cache_name, max_age_seconds=10 * 60)
    if cache:
        return cache

    data = _jira_get(
        base_url,
        headers,
        "/rest/api/3/user/assignable/search",
        params={"project": project_key, "maxResults": "50"},
    )

    out: List[Dict[str, str]] = []
    for u in data:
        account_id = u.get("accountId", "")
        display = u.get("displayName", "")
        if account_id and display:
            out.append({"accountId": account_id, "displayName": display})

    out.sort(key=lambda x: x["displayName"])
    _save_cache(cache_name, out)
    return out


def _get_epic_link_field_id(base_url: str, headers: Dict[str, str]) -> Optional[str]:
    cache = _load_cache("fields.json", max_age_seconds=24 * 3600)
    if not cache:
        cache = _jira_get(base_url, headers, "/rest/api/3/field")
        _save_cache("fields.json", cache)

    candidates = {
        "epic link",
        "vínculo com épico",
        "vinculo com epico",
        "link do épico",
        "link do epico",
    }

    for f in cache:
        name = (f.get("name") or "").strip().lower()
        if name in candidates:
            return f.get("id")

    for f in cache:
        schema = f.get("schema") or {}
        custom = str(schema.get("custom") or "").lower()
        if custom in {"com.pyxis.greenhopper.jira:gh-epic-link", "gh-epic-link"}:
            return f.get("id")

    return None


# ----------------------------
# UI
# ----------------------------
def _run_yad_form(
    projects: List[Dict[str, str]],
    issue_types: List[Dict[str, str]],
    epics: List[Dict[str, str]],
    assignees: List[Dict[str, str]],
    default_project_key: str,
) -> Optional[Dict[str, str]]:
    project_items = [f'{p["key"]} - {p["name"]}' for p in projects]
    if default_project_key:
        project_items.sort(key=lambda s: (0 if s.startswith(default_project_key + " ") else 1, s))

    issuetype_items = [it["name"] for it in issue_types] or ["Story", "Bug", "Task"]
    epic_items = ["No Epic"] + [f'{e["key"]} - {e["summary"]}' for e in epics]
    assignee_items = ["Unassigned"] + [f'{a["displayName"]} ({a["accountId"][:8]})' for a in assignees]

    cmd = [
        "yad",
        "--form",
        "--title=Create Jira Issue",
        "--width=860",
        "--height=580",
        "--center",
        "--on-top",
        "--modal",
        "--fixed",
        "--skip-taskbar",
        "--separator=|",
        "--borders=22",
        "--button-layout=end",
        "--field=Project:CB",
        "!".join(project_items) if project_items else "",
        "--field=Issue Type:CB",
        "!".join(issuetype_items),
        "--field=Summary",
        "",
        "--field=Epic:CB",
        "!".join(epic_items),
        "--field=Description:TXT",
        "",
        "--field=Assignee:CB",
        "!".join(assignee_items),
        "--button=Create Issue:0",
        "--button=Cancel:1",
    ]

    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        return None

    raw = p.stdout.strip()
    parts = raw.split("|")
    if len(parts) < 6:
        return None

    return {
        "project": parts[0].strip(),
        "issuetype": parts[1].strip(),
        "summary": parts[2].strip(),
        "epic": parts[3].strip(),
        "description": parts[4],
        "assignee": parts[5].strip(),
    }


# ----------------------------
# Parsing
# ----------------------------
def _parse_project_key(project_field: str) -> str:
    return project_field.split(" - ", 1)[0].strip().upper()


def _find_issuetype_id(issue_types: List[Dict[str, str]], name: str) -> Optional[str]:
    name_norm = name.strip().lower()
    for it in issue_types:
        if it["name"].strip().lower() == name_norm:
            return it["id"]
    return None


def _parse_epic_key(epic_field: str) -> Optional[str]:
    if not epic_field or epic_field.lower().startswith("no epic"):
        return None
    return epic_field.split(" - ", 1)[0].strip().upper()


def _parse_assignee_account_id(assignee_field: str, assignees: List[Dict[str, str]]) -> Optional[str]:
    if not assignee_field or assignee_field.lower().startswith("unassigned"):
        return None

    if "(" in assignee_field and ")" in assignee_field:
        prefix = assignee_field.split("(", 1)[1].split(")", 1)[0].strip()
        for a in assignees:
            if a["accountId"].startswith(prefix):
                return a["accountId"]

    display = assignee_field.split(" (", 1)[0].strip()
    matches = [a for a in assignees if a["displayName"] == display]
    return matches[0]["accountId"] if matches else None


# ----------------------------
# Create issue with epic support
# ----------------------------
def create_issue_with_epic(
    base_url: str,
    headers: Dict[str, str],
    fields: Dict[str, Any],
    epic_key: Optional[str],
    epic_link_field_id: Optional[str],
) -> Any:
    if epic_key:
        fields_try = dict(fields)
        fields_try["parent"] = {"key": epic_key}
        try:
            return _jira_post(base_url, headers, "/rest/api/3/issue", {"fields": fields_try})
        except requests.HTTPError as e:
            body = e.response.text if e.response is not None else ""
            if "parent" not in body.lower() and "epic" not in body.lower():
                raise

    if epic_key and epic_link_field_id:
        fields_try = dict(fields)
        fields_try[epic_link_field_id] = epic_key
        return _jira_post(base_url, headers, "/rest/api/3/issue", {"fields": fields_try})

    return _jira_post(base_url, headers, "/rest/api/3/issue", {"fields": fields})


# ----------------------------
# Main
# ----------------------------
def main() -> int:
    prefs = _read_prefs()

    base_url = prefs["base_url"]
    email = prefs["email"]
    api_token = prefs["api_token"]
    default_project_key = prefs["default_project_key"]

    if not base_url or not email or not api_token:
        _notify("Jira Create", "Missing config: base_url / email / api_token")
        return 2

    log("=== run ===")
    log(f"base_url={base_url!r} email_set={bool(email)} token_set={bool(api_token)}")
    log(
        "env "
        f"DISPLAY={os.environ.get('DISPLAY')!r} "
        f"WAYLAND_DISPLAY={os.environ.get('WAYLAND_DISPLAY')!r} "
        f"XDG_RUNTIME_DIR={os.environ.get('XDG_RUNTIME_DIR')!r}"
    )

    headers = _jira_headers(email, api_token)

    try:
        projects = _get_projects(base_url, headers)

        preload_project_key = default_project_key or (projects[0]["key"] if projects else "")
        issue_types = _get_createmeta_issue_types(base_url, headers, preload_project_key) if preload_project_key else []
        epics = _get_epics(base_url, headers, preload_project_key) if preload_project_key else []
        assignees = _get_assignees(base_url, headers, preload_project_key) if preload_project_key else []

        form = _run_yad_form(projects, issue_types, epics, assignees, default_project_key)
        if not form:
            return 0

        project_key = _parse_project_key(form["project"])
        summary = form["summary"].strip()
        if not summary:
            _notify("Jira Create", "Summary is required.")
            return 3

        if project_key and project_key != preload_project_key:
            issue_types = _get_createmeta_issue_types(base_url, headers, project_key)
            epics = _get_epics(base_url, headers, project_key)
            assignees = _get_assignees(base_url, headers, project_key)

            form2 = _run_yad_form(projects, issue_types, epics, assignees, project_key)
            if not form2:
                return 0
            form = form2

        issuetype_id = _find_issuetype_id(issue_types, form["issuetype"])
        if not issuetype_id:
            _notify("Jira Create", f'Could not resolve issue type id for "{form["issuetype"]}".')
            return 4

        epic_key = _parse_epic_key(form["epic"])
        assignee_account_id = _parse_assignee_account_id(form["assignee"], assignees)

        epic_link_field_id = _get_epic_link_field_id(base_url, headers)

        fields: Dict[str, Any] = {
            "project": {"key": project_key},
            "issuetype": {"id": issuetype_id},
            "summary": summary,
            "description": _adf_from_text(form["description"] or ""),
        }

        if assignee_account_id:
            fields["assignee"] = {"accountId": assignee_account_id}

        created = create_issue_with_epic(base_url, headers, fields, epic_key, epic_link_field_id)
        issue_key = created.get("key")
        if not issue_key:
            _notify("Jira Create", "Issue created, but no key returned.")
            return 5

        issue_url = f"{base_url}/browse/{issue_key}"
        _wl_copy(issue_key)
        _notify("Jira Create", f"Created {issue_key} (copied to clipboard)")
        _open_url(issue_url)
        return 0

    except requests.HTTPError as e:
        body_text = e.response.text if e.response is not None else str(e)
        show_error_dialog("Jira Create – HTTP Error", body_text)
        return 10
    except Exception as e:
        show_error_dialog("Jira Create – Error", repr(e))
        return 11


if __name__ == "__main__":
    raise SystemExit(main())
