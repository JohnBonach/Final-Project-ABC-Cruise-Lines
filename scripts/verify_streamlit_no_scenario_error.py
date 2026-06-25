"""Reload page, click Run Analysis, and check for scenarios.json error."""
import json
import sys
import time
import urllib.request
import websocket


def main():
    port = 9333
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5) as r:
        targets = json.loads(r.read())
    page = next((t for t in targets if t.get("type") == "page"), None)
    ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=10)
    msg_id = 0

    def send(method, params=None):
        nonlocal msg_id
        msg_id += 1
        ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == msg_id:
                if msg.get("error"):
                    raise RuntimeError(f"{method} error: {msg['error']}")
                return msg.get("result", {})

    send("Page.enable")
    send("Runtime.enable")

    # Reload the page fresh
    send("Page.reload", {"ignoreCache": True})
    print("Reloaded page, waiting for Streamlit...")
    time.sleep(6)

    # Check initial load for errors
    expr = (
        "(() => {"
        "  const text = document.body.innerText || '';"
        "  const hasScenarioErr = /scenarios\\.json/i.test(text);"
        "  const hasErrno = /Errno/i.test(text);"
        "  const errors = Array.from(document.querySelectorAll('[data-testid=\"stException\"], .stException'));"
        "  return JSON.stringify({textLen: text.length, hasScenarioErr, hasErrno, errorCount: errors.length, errorTexts: errors.map(e => e.innerText.slice(0,300)), sample: text.slice(0,500)});"
        "})()"
    )
    result = send("Runtime.evaluate", {"expression": expr, "returnByValue": True})
    val = result.get("result", {}).get("value", "{}")
    print("AFTER RELOAD:", val[:1500].encode("ascii", "replace").decode("ascii"))

    # Click Run Analysis
    click_expr = (
        "(() => {"
        "  const btns = Array.from(document.querySelectorAll('button'));"
        "  const run = btns.find(b => /Run Analysis/i.test(b.innerText));"
        "  if (!run) return JSON.stringify({clicked:false});"
        "  run.click();"
        "  return JSON.stringify({clicked:true});"
        "})()"
    )
    result = send("Runtime.evaluate", {"expression": click_expr, "returnByValue": True})
    print("CLICK:", result.get("result", {}).get("value", "{}"))

    # Wait and poll for content + errors
    for i in range(20):
        time.sleep(2)
        check_expr = (
            "(() => {"
            "  const text = document.body.innerText || '';"
            "  const hasScenarioErr = /scenarios\\.json/i.test(text);"
            "  const hasErrno = /Errno/i.test(text);"
            "  const errors = Array.from(document.querySelectorAll('[data-testid=\"stException\"], .stException'));"
            "  const hasRec = /Recommended In-House Staffing|recommendation/i.test(text);"
            "  const hasOutlook = /P25|P50|P90|outlook|demand/i.test(text);"
            "  return JSON.stringify({textLen: text.length, hasScenarioErr, hasErrno, errorCount: errors.length, hasRec, hasOutlook, sample: text.slice(0,400)});"
            "})()"
        )
        result = send("Runtime.evaluate", {"expression": check_expr, "returnByValue": True})
        val = result.get("result", {}).get("value", "{}")
        print(f"POLL {i}: {val[:600].encode('ascii', 'replace').decode('ascii')}")
        try:
            data = json.loads(val)
            if data.get("hasScenarioErr"):
                print("!!! SCENARIOS.JSON ERROR DETECTED !!!")
                break
            if data.get("textLen", 0) > 2000 and data.get("hasRec") and data.get("hasOutlook") and not data.get("hasScenarioErr"):
                print("SUCCESS: full content rendered, no scenarios.json error")
                break
        except Exception:
            pass

    ws.close()


if __name__ == "__main__":
    main()
