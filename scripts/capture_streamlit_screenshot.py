"""Capture rendered Streamlit UI screenshots via Chrome DevTools Protocol.

Usage: python scripts/capture_streamlit_screenshot.py <debug_port> <out_dir>
"""
import json
import os
import sys
import time
import urllib.request

import websocket


def list_targets(port):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5) as r:
        return json.loads(r.read())


def connect_page(port):
    targets = list_targets(port)
    page = next((t for t in targets if t.get("type") == "page"), None)
    if not page:
        raise RuntimeError("No page target found")
    ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=10)
    return ws


def send(ws, method, params=None, msg_id=None):
    if msg_id is None:
        msg_id = send._id = getattr(send, "_id", 0) + 1
    payload = {"id": msg_id, "method": method, "params": params or {}}
    ws.send(json.dumps(payload))
    while True:
        raw = ws.recv()
        msg = json.loads(raw)
        if msg.get("id") == msg_id:
            if msg.get("error"):
                raise RuntimeError(f"{method} error: {msg['error']}")
            return msg.get("result", {})


def click_run_analysis(ws):
    """Click the Run Analysis button to populate the result sections."""
    # Streamlit buttons are <button kind="primary"> or <button> with text.
    expr = (
        "(() => {"
        "  const btns = Array.from(document.querySelectorAll('button'));"
        "  const run = btns.find(b => /Run Analysis/i.test(b.innerText));"
        "  if (!run) return JSON.stringify({clicked:false, reason:'not found', buttons: btns.map(b=>b.innerText)});"
        "  run.click();"
        "  return JSON.stringify({clicked:true, text: run.innerText});"
        "})()"
    )
    result = send(ws, "Runtime.evaluate", {"expression": expr, "returnByValue": True})
    val = result.get("result", {}).get("value", "{}")
    print("Click result:", val[:500].encode("ascii", "replace").decode("ascii"))
    return "true" in val[:60].lower()


def wait_for_content(ws, timeout_s=30.0):
    """Poll DOM until Streamlit main content block exists with visible text."""
    deadline = time.time() + timeout_s
    last_count = 0
    while time.time() < deadline:
        result = send(
            ws,
            "Runtime.evaluate",
            {
                "expression": (
                    "(() => {"
                    "  const s = document.querySelector('section.st-main, section.main, [data-testid=\"stMain\"]');"
                    "  const blocks = document.querySelectorAll('[data-testid=\"stMarkdownContainer\"], .stMarkdown, p, h1, h2, h3');"
                    "  const text = (s ? s.innerText : document.body.innerText) || '';"
                    "  return JSON.stringify({hasSection: !!s, textLen: text.length, blocks: blocks.length, sample: text.slice(0, 200)});"
                    "})()"
                ),
                "returnByValue": True,
            },
        )
        val = result.get("result", {}).get("value", "{}")
        try:
            data = json.loads(val)
        except Exception:
            data = {}
        text_len = data.get("textLen", 0)
        blocks = data.get("blocks", 0)
        sample = data.get("sample", "")
        print(f"  wait: textLen={text_len} blocks={blocks} sample={sample!a}")
        if text_len > 500 and blocks > 5:
            return True
        last_count = blocks
        time.sleep(1.0)
    return False


def wait_for_analysis_content(ws, timeout_s=45.0):
    """Poll DOM until recommendation/analysis sections appear after Run Analysis."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        result = send(
            ws,
            "Runtime.evaluate",
            {
                "expression": (
                    "(() => {"
                    "  const text = document.body.innerText || '';"
                    "  const hasRec = /Recommended In-House Staffing|recommendation|coverage/i.test(text);"
                    "  const hasOutlook = /P25|P50|P90|outlook|demand/i.test(text);"
                    "  const hasTable = /risk|cost|staffing/i.test(text);"
                    "  return JSON.stringify({textLen: text.length, hasRec, hasOutlook, hasTable, sample: text.slice(0,300)});"
                    "})()"
                ),
                "returnByValue": True,
            },
        )
        val = result.get("result", {}).get("value", "{}")
        try:
            data = json.loads(val)
        except Exception:
            data = {}
        print(
            f"  analysis-wait: textLen={data.get('textLen',0)} "
            f"hasRec={data.get('hasRec')} hasOutlook={data.get('hasOutlook')} "
            f"hasTable={data.get('hasTable')}"
        )
        if data.get("textLen", 0) > 2000 and data.get("hasRec") and data.get("hasOutlook"):
            return True
        time.sleep(1.5)
    return False


def capture(ws, out_path, full_page=True):
    params = {"format": "png", "captureBeyondViewport": full_page}
    if full_page:
        params["fromSurface"] = True
    result = send(ws, "Page.captureScreenshot", params)
    data = result.get("data")
    if not data:
        raise RuntimeError("No screenshot data returned")
    import base64

    with open(out_path, "wb") as f:
        f.write(base64.b64decode(data))
    return os.path.getsize(out_path)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    port = int(sys.argv[1])
    out_dir = sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)

    ws = connect_page(port)
    try:
        send(ws, "Page.enable")
        send(ws, "Runtime.enable")
        print("Waiting for Streamlit content to render...")
        ok = wait_for_content(ws, timeout_s=45.0)
        if not ok:
            print("WARNING: content threshold not reached, capturing anyway")

        # Capture initial state (header + buttons)
        out_initial = os.path.join(out_dir, "streamlit_ui_initial.png")
        size = capture(ws, out_initial, full_page=False)
        print(f"Saved initial screenshot: {out_initial} ({size} bytes)")

        # Click Run Analysis to populate result sections
        print("Clicking Run Analysis...")
        clicked = click_run_analysis(ws)
        if clicked:
            print("Waiting for analysis sections to render...")
            ok2 = wait_for_analysis_content(ws, timeout_s=60.0)
            if not ok2:
                print("WARNING: analysis sections threshold not reached")
            time.sleep(2.0)
        else:
            print("WARNING: could not click Run Analysis")
        # Scroll to load lazy content and allow re-render
        send(
            ws,
            "Runtime.evaluate",
            {"expression": "window.scrollTo(0, document.body.scrollHeight)"},
        )
        time.sleep(1.5)
        send(
            ws,
            "Runtime.evaluate",
            {"expression": "window.scrollTo(0, 0)"},
        )
        time.sleep(1.0)

        out_top = os.path.join(out_dir, "streamlit_ui_top.png")
        size = capture(ws, out_top, full_page=False)
        print(f"Saved viewport screenshot: {out_top} ({size} bytes)")

        out_full = os.path.join(out_dir, "streamlit_ui_full.png")
        # Capture full page by setting a large clip via metrics
        # Use captureBeyondViewport true
        size = capture(ws, out_full, full_page=True)
        print(f"Saved full-page screenshot: {out_full} ({size} bytes)")

        # Capture DOM summary for inspection
        result = send(
            ws,
            "Runtime.evaluate",
            {
                "expression": (
                    "(() => {"
                    "  const headings = Array.from(document.querySelectorAll('h1,h2,h3')).map(e => e.innerText.trim()).filter(Boolean);"
                    "  const sectionLabels = Array.from(document.querySelectorAll('[data-testid=\"stHeading\"]')).map(e => e.innerText.trim()).filter(Boolean);"
                    "  const bodyLen = document.body.innerText.length;"
                    "  return JSON.stringify({bodyLen, headings, sectionLabels});"
                    "})()"
                ),
                "returnByValue": True,
            },
        )
        val = result.get("result", {}).get("value", "{}")
        print("DOM summary:", val[:2000].encode("ascii", "replace").decode("ascii"))
    finally:
        ws.close()


if __name__ == "__main__":
    main()
