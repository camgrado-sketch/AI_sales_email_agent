import base64
import mimetypes
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

from email_agent import config, data_store, template_importer


def _guess_mime(path):
    mime, _ = mimetypes.guess_type(path)
    return mime or "image/png"


def _inline_images(html, images):
    """Replace cid:xxx references with base64 data URIs for offline preview."""
    cid_map = {}
    for img in images:
        path = img.get("path", "")
        cid = img.get("cid", "")
        if not path or not cid or not os.path.exists(path):
            continue
        try:
            with open(path, "rb") as f:
                data = base64.b64encode(f.read()).decode("utf-8")
            mime = _guess_mime(path)
            cid_map[cid] = f"data:{mime};base64,{data}"
        except Exception:
            pass

    def replace_cid(match):
        cid = match.group(1).strip()
        return cid_map.get(cid, f"<!-- missing image: {cid} -->")

    return re.sub(r'cid:([^"\'\s\)\>]+)', replace_cid, html)


def _is_wsl():
    """Detect Windows Subsystem for Linux."""
    if os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP"):
        return True
    try:
        with open("/proc/sys/kernel/osrelease", "r", encoding="utf-8") as f:
            release = f.read().lower()
            return "microsoft" in release or "wsl" in release
    except Exception:
        return False


def _has_gui():
    """Return True when the environment is likely to support a headed browser.

    macOS and Windows are assumed to have a GUI. On Linux, require a DISPLAY
    environment variable and exclude WSL/SSH-like headless environments.
    """
    if sys.platform == "darwin" or sys.platform.startswith("win"):
        return True
    if _is_wsl():
        return False
    return bool(os.environ.get("DISPLAY"))


def _open_with_browser_command(cmd, path):
    """Open path with a user-configured browser command."""
    try:
        if "%s" in cmd:
            full_cmd = cmd.replace("%s", path)
            subprocess.Popen(full_cmd, shell=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            parts = shlex.split(cmd)
            subprocess.Popen(parts + [path],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        print(f"⚠️ Could not open with configured browser '{cmd}': {e}")
        return False


def _open_wsl_browser(path):
    """Try WSL-specific ways to open a file in the Windows default browser."""
    commands = [
        ["wslview", path],
        ["powershell.exe", "-Command", f'Start-Process "{path}"'],
        ["cmd.exe", "/c", "start", "", path],
    ]
    for cmd in commands:
        try:
            if shutil.which(cmd[0]) is None:
                continue
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            print(f"⚠️ Could not open with {cmd[0]}: {e}")
    return False


def _copy_to_latest_preview(path):
    """Keep a stable fallback copy so the user can open it manually."""
    try:
        latest = os.path.join(config.DATA_DIR, "latest_preview.html")
        shutil.copy2(path, latest)
        return latest
    except Exception:
        return None


def _write_temp_html(html, suffix=".html"):
    """Write HTML to a temp file and return the path."""
    fd, path = tempfile.mkstemp(suffix=suffix, prefix="email_agent_", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(html)
    except Exception:
        os.close(fd)
        raise
    return path


def _open_with_playwright(path, headless=False):
    """Try to open the file URL using Playwright Chromium."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            page = browser.new_page()
            page.goto(f"file://{path}")
            if headless:
                screenshot_path = os.path.join(config.DATA_DIR, "latest_preview.png")
                os.makedirs(config.DATA_DIR, exist_ok=True)
                page.screenshot(path=screenshot_path, full_page=True)
                print(
                    f"\033[1m\033[93m📸 已生成 PNG 预览：{screenshot_path}\033[0m"
                )
            # Keep the browser open in headed mode until the user closes it.
            # In headless mode we close immediately after screenshot.
            if not headless:
                input("\n[Enter] 关闭浏览器预览并继续...")
            browser.close()
        return True
    except Exception as e:
        if headless:
            print(f"⚠️ Playwright headless 截图失败：{e}")
        else:
            print(f"⚠️ Playwright headed 启动失败（可能无桌面环境）：{e}")
        return False


def _open_with_system_browser(path):
    """Fallback to the system default browser or BROWSER env command."""
    import webbrowser

    opened = False
    browser_cmd = (config.BROWSER or os.environ.get("BROWSER", "")).strip()

    if browser_cmd:
        opened = _open_with_browser_command(browser_cmd, path)

    if not opened:
        try:
            opened = bool(webbrowser.open(f"file://{path}"))
        except Exception as e:
            print(f"⚠️ Could not open browser: {e}")

    if not opened and _is_wsl():
        opened = _open_wsl_browser(path)

    return opened


def _open_html(html, suffix=".html"):
    """Write HTML to a temp file and open it with Playwright, falling back as needed.

    On systems with a GUI (macOS/Windows, or Linux with DISPLAY and not WSL),
    try Playwright headed first. Otherwise go straight to a headless screenshot.
    """
    path = _write_temp_html(html, suffix=suffix)

    if _has_gui():
        # Primary: Playwright headed Chromium
        if _open_with_playwright(path, headless=False):
            return path

        # Fallback: Playwright headless screenshot
        if _open_with_playwright(path, headless=True):
            _copy_to_latest_preview(path)
            print(f"🌐 临时 HTML 文件：{path}")
            return path
    else:
        # Headless environments: screenshot directly, no invalid headed attempt
        if _open_with_playwright(path, headless=True):
            _copy_to_latest_preview(path)
            print(f"🌐 临时 HTML 文件：{path}")
            return path

    # Fallback: system browser / webbrowser / WSL
    if _open_with_system_browser(path):
        return path

    # Final fallback: print paths
    latest = _copy_to_latest_preview(path)
    print("⚠️ 无法自动打开预览，请手动打开：")
    print(f"   {path}")
    if latest:
        print(f"   稳定副本：{latest}")
    return path


def _words(text, n=50):
    """Return the first n words/chunks of text."""
    if not text:
        return ""
    # Treat CJK characters as individual words for Chinese excerpts
    tokens = re.findall(r"[一-龥]|[^一-龥\s]+", text)
    if len(tokens) <= n:
        return text.strip()
    return "".join(tokens[:n]).strip() + "..."


def open_draft_preview(draft):
    """Open a browser preview of a single draft email."""
    html_body = draft.get("html_body", "")
    images = draft.get("images", [])
    html_body = _inline_images(html_body, images)

    subject = draft.get("subject", "")
    customer = draft.get("customer_id", "")
    rendered_by = draft.get("rendered_by", "local")

    banner = f"""
    <div style="background:#fff3cd;border:1px solid #ffeaa7;padding:12px 16px;border-radius:6px;margin-bottom:24px;font-family:sans-serif;">
      <strong>Draft Preview</strong> — {subject}<br>
      <small>Customer: {customer} | Rendered by: {rendered_by}</small>
    </div>
    """

    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Draft Preview: {subject}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 760px; margin: 40px auto; padding: 20px; line-height: 1.6; }}
    </style>
</head>
<body>
    {banner}
    {html_body}
</body>
</html>
"""
    return _open_html(full_html, suffix="_draft.html")


def open_template_preview(template_name):
    """Open a browser preview of an active template with placeholders highlighted."""
    preview_html = template_importer.build_preview_html(template_name)
    return _open_html(preview_html, suffix="_template.html")


def open_replies_preview(replies):
    """Open a browser preview of matched replies."""
    email_logs = {r.get("email_id"): r for r in data_store.load_email_logs()}

    items = []
    for reply in replies:
        email_id = reply.get("email_id", "")
        original = email_logs.get(email_id, {})
        original_subject = original.get("subject", "(unknown)")
        reply_subject = reply.get("reply_subject", "")
        sender = reply.get("sender", "")
        receive_time = reply.get("receive_time", "")
        excerpt = _words(reply.get("body_excerpt", ""), n=50)
        full_body = reply.get("full_body", "").replace("\n", "<br>")

        items.append(f"""
        <div style="border:1px solid #dee2e6;border-radius:8px;padding:16px;margin-bottom:16px;">
          <h3 style="margin-top:0;">{reply_subject or '(no subject)'}</h3>
          <p><strong>From:</strong> {sender} <strong>At:</strong> {receive_time}</p>
          <p><strong>Original email:</strong> {original_subject}</p>
          <div style="background:#f8f9fa;padding:12px;border-radius:4px;margin:12px 0;">
            <strong>Excerpt:</strong> {excerpt}
          </div>
          <details>
            <summary>Full reply ({len(reply.get('full_body',''))} chars)</summary>
            <div style="margin-top:12px;">{full_body}</div>
          </details>
        </div>
        """)

    items_html = "\n".join(items) if items else "<p>No replies found.</p>"

    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Replies Preview</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 760px; margin: 40px auto; padding: 20px; line-height: 1.6; }}
        summary {{ cursor: pointer; color: #0d6efd; }}
    </style>
</head>
<body>
    <h1>Matched Replies ({len(replies)})</h1>
    {items_html}
</body>
</html>
"""
    return _open_html(full_html, suffix="_replies.html")
