import base64
import mimetypes
import os
import re
import tempfile
import webbrowser

from email_agent import config, data_store


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


def _open_html(html, suffix=".html"):
    """Write HTML to a temp file and open it in the default browser."""
    fd, path = tempfile.mkstemp(suffix=suffix, prefix="email_agent_", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(html)
    except Exception:
        os.close(fd)
        raise
    try:
        webbrowser.open(f"file://{path}")
    except Exception as e:
        print(f"⚠️ Could not open browser: {e}")
        print(f"   Preview saved to: {path}")
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
    model = draft.get("model_used", "")
    meta = draft.get("generation_meta", {})

    banner = f"""
    <div style="background:#fff3cd;border:1px solid #ffeaa7;padding:12px 16px;border-radius:6px;margin-bottom:24px;font-family:sans-serif;">
      <strong>Draft Preview</strong> — {subject}<br>
      <small>Customer: {customer} | Model: {model} | Tokens: {meta.get('total_tokens', 0)} | Generated: {meta.get('generation_time', '')}</small>
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
