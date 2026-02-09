#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
import threading
import time
import webbrowser
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, GObject, Gtk  # noqa: E402


CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "ulauncher-jira-create")
os.makedirs(CACHE_DIR, exist_ok=True)


# ----------------------------
# Preferences / Cache
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
# Jira API
# ----------------------------
def _jira_headers(email: str, api_token: str) -> Dict[str, str]:
    basic = base64.b64encode(f"{email}:{api_token}".encode("utf-8")).decode("utf-8")
    return {
        "Authorization": f"Basic {basic}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _jira_get(base_url: str, headers: Dict[str, str], path: str, params: Optional[Dict[str, str]] = None) -> Any:
    r = requests.get(f"{base_url}{path}", headers=headers, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def _jira_post(base_url: str, headers: Dict[str, str], path: str, payload: Any) -> Any:
    r = requests.post(f"{base_url}{path}", headers=headers, json=payload, timeout=25)
    r.raise_for_status()
    return r.json()


def _adf_from_text(text: str) -> Dict[str, Any]:
    lines = text.splitlines() if text else []
    content: List[Dict[str, Any]] = []

    if not lines:
        content.append({"type": "paragraph", "content": [{"type": "text", "text": ""}]})
    else:
        for line in lines:
            content.append({"type": "paragraph", "content": [{"type": "text", "text": line}]})

    return {"type": "doc", "version": 1, "content": content}


def get_projects(base_url: str, headers: Dict[str, str]) -> List[Dict[str, str]]:
    cache = _load_cache("projects.json", 24 * 3600)
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


def get_issue_types(base_url: str, headers: Dict[str, str], project_key: str) -> List[Dict[str, str]]:
    cache_name = f"issuetypes_{project_key}.json"
    cache = _load_cache(cache_name, 24 * 3600)
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


def get_epics(base_url: str, headers: Dict[str, str], project_key: str) -> List[Dict[str, str]]:
    cache_name = f"epics_{project_key}.json"
    cache = _load_cache(cache_name, 10 * 60)
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
        {"key": i.get("key", ""), "summary": (i.get("fields", {}) or {}).get("summary", "")}
        for i in issues
        if i.get("key")
    ]
    _save_cache(cache_name, out)
    return out


def get_assignees(base_url: str, headers: Dict[str, str], project_key: str) -> List[Dict[str, str]]:
    cache_name = f"assignees_{project_key}.json"
    cache = _load_cache(cache_name, 10 * 60)
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


def get_epic_link_field_id(base_url: str, headers: Dict[str, str]) -> Optional[str]:
    cache = _load_cache("fields.json", 24 * 3600)
    if not cache:
        cache = _jira_get(base_url, headers, "/rest/api/3/field")
        _save_cache("fields.json", cache)

    candidates = {"epic link", "vínculo com épico", "vinculo com epico", "link do épico", "link do epico"}
    for f in cache:
        if (f.get("name") or "").strip().lower() in candidates:
            return f.get("id")

    for f in cache:
        schema = f.get("schema") or {}
        custom = str(schema.get("custom") or "").lower()
        if custom in {"com.pyxis.greenhopper.jira:gh-epic-link", "gh-epic-link"}:
            return f.get("id")

    return None


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
# UI model for dropdowns
# ----------------------------
@dataclass(frozen=True)
class ComboItem:
    id: str
    label: str


class ComboStringList(Gtk.StringList):
    def __init__(self, items: List[ComboItem]):
        super().__init__()
        self.items = items
        for it in items:
            self.append(it.label)

    def get_item(self, index: int) -> Optional[ComboItem]:
        if 0 <= index < len(self.items):
            return self.items[index]
        return None


# ----------------------------
# Libadwaita App
# ----------------------------
class JiraCreateWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application, prefs: Dict[str, str]):
        super().__init__(application=app)
        self.set_title("Create Jira Issue")
        self.set_default_size(820, 560)
        self.set_resizable(False)
        self.set_hide_on_close(True)
        self.set_deletable(True)
        self.set_modal(True)
        self.set_focusable(True)
        self.set_can_focus(True)


        self.prefs = prefs
        self.base_url = prefs["base_url"]
        self.headers = _jira_headers(prefs["email"], prefs["api_token"])
        self.default_project_key = prefs["default_project_key"]

        self.projects: List[Dict[str, str]] = []
        self.issue_types: List[Dict[str, str]] = []
        self.epics: List[Dict[str, str]] = []
        self.assignees: List[Dict[str, str]] = []

        self.epic_link_field_id: Optional[str] = None

        self._build_ui()
        self._load_initial_data_async()

    def _build_ui(self) -> None:
        header = Adw.HeaderBar()

        self.create_btn = Gtk.Button(label="Create")
        self.create_btn.add_css_class("suggested-action")
        self.create_btn.connect("clicked", self._on_create_clicked)

        self.cancel_btn = Gtk.Button(label="Cancel")
        self.cancel_btn.connect("clicked", lambda *_: self.close())

        self.spinner = Gtk.Spinner()

        header.pack_start(self.spinner)
        header.pack_end(self.cancel_btn)
        header.pack_end(self.create_btn)

        self.toast_overlay = Adw.ToastOverlay()

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(header)
        toolbar_view.set_content(self.toast_overlay)

        self.set_content(toolbar_view)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.toast_overlay.set_child(scroller)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        root.set_margin_top(18)
        root.set_margin_bottom(18)
        root.set_margin_start(18)
        root.set_margin_end(18)
        scroller.set_child(root)

        title = Gtk.Label(label="Create Issue")
        title.set_xalign(0)
        title.add_css_class("title-1")
        subtitle = Gtk.Label(label="Fill the fields below. Description supports plain text.")
        subtitle.set_xalign(0)
        subtitle.add_css_class("dim-label")

        root.append(title)
        root.append(subtitle)

        self.status = Gtk.Label(label="")
        self.status.set_xalign(0)
        self.status.add_css_class("dim-label")
        root.append(self.status)

        group = Adw.PreferencesGroup()
        root.append(group)

        self.project_row = Adw.ComboRow(title="Project")
        group.add(self.project_row)

        self.type_row = Adw.ComboRow(title="Issue Type")
        group.add(self.type_row)

        self.summary_row = Adw.EntryRow(title="Summary")
        self.summary_row.set_show_apply_button(False)
        group.add(self.summary_row)

        self.epic_row = Adw.ComboRow(title="Epic")
        group.add(self.epic_row)

        self.assignee_row = Adw.ComboRow(title="Assignee")
        group.add(self.assignee_row)

        desc_group = Adw.PreferencesGroup()
        root.append(desc_group)

        desc_title = Adw.ActionRow(title="Description")
        desc_title.set_subtitle("Plain text (we convert to Jira ADF)")
        desc_group.add(desc_title)

        self.desc_view = Gtk.TextView()
        self.desc_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.desc_view.set_top_margin(8)
        self.desc_view.set_bottom_margin(8)
        self.desc_view.set_left_margin(8)
        self.desc_view.set_right_margin(8)
        self.desc_view.add_css_class("boxed-list")

        desc_frame = Gtk.Frame()
        desc_frame.set_child(self.desc_view)
        root.append(desc_frame)

    def _set_busy(self, busy: bool, message: str = "") -> None:
        self.create_btn.set_sensitive(not busy)
        self.cancel_btn.set_sensitive(not busy)
        self.status.set_text(message)

        if busy:
            self.spinner.start()
        else:
            self.spinner.stop()

    def _toast(self, text: str) -> None:
        self.toast_overlay.add_toast(Adw.Toast.new(text))

    def _get_desc_text(self) -> str:
        buf = self.desc_view.get_buffer()
        start = buf.get_start_iter()
        end = buf.get_end_iter()
        return buf.get_text(start, end, True)

    def _load_initial_data_async(self) -> None:
        if not self.base_url or not self.prefs["email"] or not self.prefs["api_token"]:
            self._toast("Missing Jira config. Set base_url/email/token in extension preferences.")
            self._set_busy(False)
            return

        self._set_busy(True, "Loading projects…")

        def worker():
            try:
                projects = get_projects(self.base_url, self.headers)
                epic_field = get_epic_link_field_id(self.base_url, self.headers)
                GLib.idle_add(self._on_projects_loaded, projects, epic_field)
            except Exception as e:
                GLib.idle_add(self._on_error, f"{e!r}")

        threading.Thread(target=worker, daemon=True).start()

    def _on_projects_loaded(self, projects: List[Dict[str, str]], epic_field: Optional[str]) -> None:
        self.projects = projects
        self.epic_link_field_id = epic_field

        items = [ComboItem(p["key"], f'{p["key"]} — {p["name"]}') for p in self.projects]
        model = ComboStringList(items)
        self.project_row.set_model(model)

        idx = 0
        if self.default_project_key:
            for i, p in enumerate(self.projects):
                if p["key"].upper() == self.default_project_key:
                    idx = i
                    break
        self.project_row.set_selected(idx)
        self.project_row.connect("notify::selected", self._on_project_changed)

        self._load_project_deps_async(self.projects[idx]["key"])
        return False

    def _on_project_changed(self, *args) -> None:
        sel = self.project_row.get_selected()
        if sel < 0 or sel >= len(self.projects):
            return
        project_key = self.projects[sel]["key"]
        self._load_project_deps_async(project_key)

    def _load_project_deps_async(self, project_key: str) -> None:
        self._set_busy(True, f"Loading metadata for {project_key}…")

        def worker():
            try:
                types = get_issue_types(self.base_url, self.headers, project_key)
                epics = get_epics(self.base_url, self.headers, project_key)
                assignees = get_assignees(self.base_url, self.headers, project_key)
                GLib.idle_add(self._on_project_deps_loaded, types, epics, assignees)
            except requests.HTTPError as e:
                body = e.response.text if e.response is not None else str(e)
                GLib.idle_add(self._on_error, body)
            except Exception as e:
                GLib.idle_add(self._on_error, f"{e!r}")

        threading.Thread(target=worker, daemon=True).start()

    def _on_project_deps_loaded(
        self,
        types: List[Dict[str, str]],
        epics: List[Dict[str, str]],
        assignees: List[Dict[str, str]],
    ) -> None:
        self.issue_types = types
        self.epics = epics
        self.assignees = assignees

        type_items = [ComboItem(t["id"], t["name"]) for t in self.issue_types]
        self.type_row.set_model(ComboStringList(type_items))
        self.type_row.set_selected(0)

        epic_items = [ComboItem("", "No Epic")] + [
            ComboItem(e["key"], f'{e["key"]} — {e["summary"]}') for e in self.epics
        ]
        self.epic_row.set_model(ComboStringList(epic_items))
        self.epic_row.set_selected(0)

        ass_items = [ComboItem("", "Unassigned")] + [
            ComboItem(a["accountId"], a["displayName"]) for a in self.assignees
        ]
        self.assignee_row.set_model(ComboStringList(ass_items))
        self.assignee_row.set_selected(0)

        self._set_busy(False, "")
        return False

    def _on_error(self, msg: str) -> None:
        self._set_busy(False, "")
        dlg = Adw.MessageDialog.new(self, "Jira Error", "Request failed.")
        dlg.set_body(msg[:6000])
        dlg.add_response("ok", "OK")
        dlg.set_default_response("ok")
        dlg.present()
        return False

    def _on_create_clicked(self, *_args) -> None:
        sel = self.project_row.get_selected()
        if sel < 0 or sel >= len(self.projects):
            self._toast("Select a project.")
            return

        project_key = self.projects[sel]["key"]

        type_sel = self.type_row.get_selected()
        type_model = self.type_row.get_model()
        issue_type_id = ""
        if isinstance(type_model, ComboStringList):
            it = type_model.get_item(type_sel)
            issue_type_id = it.id if it else ""

        summary = (self.summary_row.get_text() or "").strip()
        if not summary:
            self._toast("Summary is required.")
            return

        epic_sel = self.epic_row.get_selected()
        epic_model = self.epic_row.get_model()
        epic_key = None
        if isinstance(epic_model, ComboStringList):
            ep = epic_model.get_item(epic_sel)
            epic_key = ep.id if ep and ep.id else None

        ass_sel = self.assignee_row.get_selected()
        ass_model = self.assignee_row.get_model()
        assignee_id = None
        if isinstance(ass_model, ComboStringList):
            a = ass_model.get_item(ass_sel)
            assignee_id = a.id if a and a.id else None

        description = self._get_desc_text()

        fields: Dict[str, Any] = {
            "project": {"key": project_key},
            "issuetype": {"id": issue_type_id},
            "summary": summary,
            "description": _adf_from_text(description),
        }
        if assignee_id:
            fields["assignee"] = {"accountId": assignee_id}

        self._set_busy(True, "Creating issue…")

        def worker():
            try:
                created = create_issue_with_epic(
                    self.base_url,
                    self.headers,
                    fields,
                    epic_key,
                    self.epic_link_field_id,
                )
                key = created.get("key", "")
                GLib.idle_add(self._on_created, key)
            except requests.HTTPError as e:
                body = e.response.text if e.response is not None else str(e)
                GLib.idle_add(self._on_error, body)
            except Exception as e:
                GLib.idle_add(self._on_error, f"{e!r}")

        threading.Thread(target=worker, daemon=True).start()

    def _on_created(self, issue_key: str) -> None:
        self._set_busy(False, "")

        if not issue_key:
            self._toast("Created, but no issue key returned.")
            return False

        try:
            clipboard = self.get_clipboard()
            clipboard.set(issue_key)
        except Exception:
            pass

        self._toast(f"Created {issue_key} (copied)")
        webbrowser.open(f"{self.base_url}/browse/{issue_key}")
        self.close()
        return False


class JiraCreateApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.jader.jira-create", flags=Gio.ApplicationFlags.FLAGS_NONE)

    def do_activate(self):
        prefs = _read_prefs()
        if not prefs["base_url"] or not prefs["email"] or not prefs["api_token"]:
            pass

        win = JiraCreateWindow(self, prefs)
        win.set_default_size(820, 860)
        win.present()


def main() -> int:
    app = JiraCreateApp()
    return app.run([])


if __name__ == "__main__":
    raise SystemExit(main())
