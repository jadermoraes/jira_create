# Jira Create - Ulauncher Extension

A powerful Ulauncher extension for quickly creating Jira issues without leaving your workflow. Create tasks, bugs, and stories with support for epics, assignees, and full issue metadata—all from a beautiful, native interface.

## ✨ Features

- **Fast Issue Creation**: Create Jira issues in seconds with a keyboard-driven workflow
- **Dual UI Modes**: Choose between modern GTK4/Libadwaita or lightweight YAD interface
- **Epic Support**: Link issues to epics automatically with smart field detection
- **Smart Caching**: Projects, issue types, epics, and assignees are cached for instant loading
- **Assignee Management**: Quickly assign issues to team members
- **Clipboard Integration**: Issue keys are automatically copied to clipboard
- **Browser Integration**: Opens newly created issues in your default browser
- **Multi-project Support**: Works with multiple Jira projects with a default project preference
- **Rich Description**: Add detailed descriptions with automatic conversion to Jira's ADF format

## 📋 Requirements

- **Ulauncher** 5.0 or higher
- **Python** 3.8+
- **Python packages**: `requests`, `pygobject` (for GTK backend)
- **System packages**:
  - GTK backend: `gtk4`, `libadwaita-1`
  - YAD backend: `yad`
  - Notifications: `notify-send` (libnotify)
  - Clipboard (YAD): `wl-copy` (for Wayland) or `xclip` (for X11)

### Installing Dependencies

#### Arch Linux / Manjaro
```bash
sudo pacman -S python-requests python-gobject gtk4 libadwaita yad libnotify wl-clipboard
```

#### Ubuntu / Debian
```bash
sudo apt install python3-requests python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 yad libnotify-bin wl-clipboard
```

#### Fedora
```bash
sudo dnf install python3-requests python3-gobject gtk4 libadwaita yad libnotify wl-clipboard
```

## 🚀 Installation

### Method 1: Via Ulauncher Extensions (Recommended)

1. Open Ulauncher preferences
2. Go to **Extensions** tab
3. Click **Add extension**
4. Paste the repository URL: `https://github.com/yourusername/ulauncher-jira-create`
5. Configure your Jira credentials (see Configuration section)

### Method 2: Manual Installation

```bash
cd ~/.local/share/ulauncher/extensions/
git clone https://github.com/yourusername/ulauncher-jira-create com.jader.jira-create
```

Then restart Ulauncher or reload extensions.

## ⚙️ Configuration

Open Ulauncher preferences → Extensions → Jira Create and configure:

| Setting | Description | Required |
|---------|-------------|----------|
| **Base URL** | Your Jira instance URL (e.g., `https://yourcompany.atlassian.net`) | Yes |
| **Email** | Your Jira account email | Yes |
| **API Token** | Jira API token ([create one here](https://id.atlassian.com/manage-profile/security/api-tokens)) | Yes |
| **Default Project Key** | Default project to preselect (e.g., `PROJ`) | No |
| **UI Backend** | Choose `gtk` (modern) or `yad` (lightweight) | No (default: gtk) |

### Creating a Jira API Token

1. Visit [Atlassian API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Click **Create API token**
3. Give it a name (e.g., "Ulauncher Extension")
4. Copy the token and paste it in the extension settings

## 📖 Usage

1. Open Ulauncher (default: `Ctrl+Space`)
2. Type your keyword (default: `jira`) and press Enter
3. The create issue form will open:
   - **Project**: Select the target project
   - **Issue Type**: Choose Story, Bug, Task, etc.
   - **Summary**: Enter a brief title (required)
   - **Epic**: Optionally link to an existing epic
   - **Description**: Add detailed information
   - **Assignee**: Assign to a team member or leave unassigned
4. Click **Create** or press `Ctrl+Enter`
5. The issue key is copied to your clipboard and opens in your browser

### Keyboard Shortcuts

- `Tab` / `Shift+Tab`: Navigate between fields
- `Ctrl+Enter`: Create issue (when in GTK mode)
- `Esc`: Cancel and close window

## 🎨 UI Backends

### GTK Backend (Recommended)

Modern interface using GTK4 and Libadwaita:
- Native Linux look and feel
- Better keyboard navigation
- Automatic dark mode support
- More responsive

### YAD Backend

Lightweight alternative using YAD:
- Minimal dependencies
- Faster startup on older systems
- Good for minimal desktop environments

Switch backends in extension preferences by setting **UI Backend** to `gtk` or `yad`.

## 🔧 Troubleshooting

### Extension doesn't appear in Ulauncher

- Restart Ulauncher: `ulauncher --no-window --no-window-shadow`
- Check logs: `tail -f ~/.cache/ulauncher/last.log`

### Issues with GTK backend

- Ensure GTK4 and Libadwaita are installed
- Check: `python3 -c "import gi; gi.require_version('Gtk', '4.0'); gi.require_version('Adw', '1')"`

### Authentication errors

- Verify your API token is correct and not expired
- Ensure your email matches your Jira account
- Check your Jira instance URL (no trailing slash)

### Epic linking not working

The extension automatically detects epic link fields in your Jira instance. If epic linking fails:
- Your Jira project might not support epics
- You may need to enable the Epic feature in project settings

### Debug logs

- GTK backend logs: Check output when running `ulauncher -v`
- YAD backend logs: Check `/tmp/jira_create_runtime.log` and `/tmp/jira_ulauncher.log`

## 🗂️ Cache

The extension caches data to improve performance:

- **Projects**: Cached for 24 hours
- **Issue Types**: Cached for 24 hours per project
- **Epics**: Cached for 10 minutes per project
- **Assignees**: Cached for 10 minutes per project

Cache location: `~/.cache/ulauncher-jira-create/`

To clear cache:
```bash
rm -rf ~/.cache/ulauncher-jira-create/
```

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes
4. Run basic tests to ensure functionality
5. Commit your changes: `git commit -m 'Add amazing feature'`
6. Push to the branch: `git push origin feature/amazing-feature`
7. Open a Pull Request

### Development Setup

```bash
git clone https://github.com/yourusername/ulauncher-jira-create
cd ulauncher-jira-create

# Test GTK backend directly
export JIRA_BASE_URL="https://yourcompany.atlassian.net"
export JIRA_EMAIL="your-email@example.com"
export JIRA_API_TOKEN="your-token"
export JIRA_DEFAULT_PROJECT_KEY="PROJ"

python3 jira_gui.py
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built for [Ulauncher](https://ulauncher.io/)
- Uses [Jira REST API v3](https://developer.atlassian.com/cloud/jira/platform/rest/v3/)
- GTK interface powered by [Libadwaita](https://gnome.pages.gitlab.gnome.org/libadwaita/)

## 📧 Support

If you encounter any issues or have questions:

- Open an issue on GitHub
- Check existing issues for solutions
- Review the troubleshooting section above

---

Made with ❤️ for productive developers
