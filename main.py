import os
import shlex

from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import KeywordQueryEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.RunScriptAction import RunScriptAction
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction


class JiraCreateExtension(Extension):
    def __init__(self):
        super().__init__()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())


class KeywordQueryEventListener(EventListener):
    def on_event(self, event, extension):
        ext_path = os.path.dirname(os.path.realpath(__file__))

        ui_backend = (extension.preferences.get("ui_backend") or "gtk").strip().lower()

        gtk_path = os.path.join(ext_path, "jira_gui.py")
        yad_path = os.path.join(ext_path, "jira_create.py")

        target_path = gtk_path if ui_backend == "gtk" else yad_path

        base_url = (extension.preferences.get("base_url") or "").rstrip("/")
        email = extension.preferences.get("email") or ""
        api_token = extension.preferences.get("api_token") or ""
        default_project_key = (extension.preferences.get("default_project_key") or "").strip().upper()

        if ui_backend == "yad":
            cmd = f'python3 {shlex.quote(yad_path)}'
        else:
            cmd = f'python3 {shlex.quote(gtk_path)}'


        bash_script = f"""#!/usr/bin/env bash
set -u

LOG="/tmp/jira_ulauncher.log"
echo "---- $(date) ----" >> "$LOG"
echo "backend={ui_backend}" >> "$LOG"
echo "target_path={shlex.quote(target_path)}" >> "$LOG"
echo "PWD=$(pwd)" >> "$LOG"
echo "PATH=$PATH" >> "$LOG"
echo "which python3: $(command -v python3 || true)" >> "$LOG"
echo "python3 --version: $(python3 --version 2>/dev/null || true)" >> "$LOG"
echo "DISPLAY=${{DISPLAY:-}}" >> "$LOG"
echo "WAYLAND_DISPLAY=${{WAYLAND_DISPLAY:-}}" >> "$LOG"
echo "XDG_RUNTIME_DIR=${{XDG_RUNTIME_DIR:-}}" >> "$LOG"

export JIRA_BASE_URL={shlex.quote(base_url)}
export JIRA_EMAIL={shlex.quote(email)}
export JIRA_API_TOKEN={shlex.quote(api_token)}
export JIRA_DEFAULT_PROJECT_KEY={shlex.quote(default_project_key)}

echo "jira_base_url=$JIRA_BASE_URL" >> "$LOG"
echo "jira_email_set=$([ -n "${{JIRA_EMAIL:-}}" ] && echo yes || echo no)" >> "$LOG"
echo "jira_token_set=$([ -n "${{JIRA_API_TOKEN:-}}" ] && echo yes || echo no)" >> "$LOG"

nohup env -i \
  HOME="$HOME" USER="$USER" PATH="$PATH" \
  DISPLAY="${{DISPLAY:-}}" WAYLAND_DISPLAY="${{WAYLAND_DISPLAY:-}}" XDG_RUNTIME_DIR="${{XDG_RUNTIME_DIR:-}}" \
  JIRA_BASE_URL="$JIRA_BASE_URL" JIRA_EMAIL="$JIRA_EMAIL" JIRA_API_TOKEN="$JIRA_API_TOKEN" JIRA_DEFAULT_PROJECT_KEY="$JIRA_DEFAULT_PROJECT_KEY" \
  {cmd} >> "$LOG" 2>&1 &

disown || true
echo "spawned pid=$!" >> "$LOG"
"""

        items = [
            ExtensionResultItem(
                icon="images/icon.png",
                name=f"Create Jira Issue ({ui_backend})",
                description="Open Jira create form (logs to /tmp/jira_ulauncher.log)",
                on_enter=RunScriptAction(bash_script),
            )
        ]
        return RenderResultListAction(items)



if __name__ == "__main__":
    JiraCreateExtension().run()
