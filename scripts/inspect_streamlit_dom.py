"""Inspect current DOM state and console logs via CDP."""
import json
import sys
import urllib.request
import websocket


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9333
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
                return msg.get("result", {})

    send("Runtime.enable")
    send("Log.enable")

    # Dump console messages accumulated
    # Check for spinner, error, status elements
    expr = (
        "(() => {"
        "  const all = Array.from(document.querySelectorAll('*'));"
        "  const spinners = all.filter(e => /stSpinner|spinner|StatusWidget|running/i.test(e.className || '') || /stSpinner/i.test(e.getAttribute('data-testid') || ''));"
        "  const errors = all.filter(e => /stException|stError|error/i.test(e.className || '') || /stException/i.test(e.getAttribute('data-testid') || ''));"
        "  const status = Array.from(document.querySelectorAll('[data-testid=\"stStatusWidget\"]'));"
        "  const buttons = Array.from(document.querySelectorAll('button')).map(b => ({text: b.innerText, disabled: b.disabled, kind: b.getAttribute('kind')}));"
        "  const bodyText = document.body.innerText;"
        "  const visibleBlocks = Array.from(document.querySelectorAll('[data-testid=\"stElement\"],[data-testid=\"stMarkdownContainer\"]')).length;"
        "  return JSON.stringify({"
        "    bodyLen: bodyText.length,"
        "    spinners: spinners.length,"
        "    spinnerClasses: spinners.slice(0,3).map(e => e.className),"
        "    errors: errors.length,"
        "    errorText: errors.slice(0,3).map(e => e.innerText.slice(0,300)),"
        "    statusWidgets: status.length,"
        "    statusText: status.map(e => e.innerText),"
        "    buttons: buttons.slice(0,10),"
        "    visibleBlocks,"
        "    bodySample: bodyText.slice(0, 1000)"
        "  });"
        "})()"
    )
    result = send("Runtime.evaluate", {"expression": expr, "returnByValue": True})
    val = result.get("result", {}).get("value", "{}")
    print(val[:4000].encode("ascii", "replace").decode("ascii"))
    ws.close()


if __name__ == "__main__":
    main()
