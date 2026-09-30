import sys
import json
import time
import urllib.request
import urllib.parse
import urllib.error

BASE_URL = "http://127.0.0.1:8000"
API_KEY = "demo-key-123"
HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

def req(method, path, data=None, is_json=True, custom_headers=None):
    url = f"{BASE_URL}{path}"
    headers = dict(HEADERS) if is_json else {"X-API-Key": API_KEY}
    if custom_headers:
        headers.update(custom_headers)
    
    body_bytes = None
    if data is not None:
        if is_json:
            body_bytes = json.dumps(data).encode("utf-8")
        elif isinstance(data, bytes):
            body_bytes = data
        else:
            body_bytes = data.encode("utf-8")

    request = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)
    start = time.time()
    try:
        with urllib.request.urlopen(request) as response:
            duration = round(time.time() - start, 3)
            res_body = response.read().decode("utf-8", errors="replace")
            res_json = json.loads(res_body) if res_body and (is_json or res_body.startswith('{')) else res_body
            return {
                "status": response.status,
                "duration": duration,
                "data": res_json
            }
    except urllib.error.HTTPError as e:
        duration = round(time.time() - start, 3)
        res_body = e.read().decode("utf-8", errors="replace")
        if e.code == 429:
            retry_after = int(e.headers.get("Retry-After", "5"))
            print(f"    [Rate Limited 429] Waiting {retry_after}s for quota reset...")
            time.sleep(retry_after)
            return req(method, path, data, is_json, custom_headers)
        try:
            res_json = json.loads(res_body)
        except:
            res_json = res_body
        return {
            "status": e.code,
            "duration": duration,
            "error": res_json
        }

print("=== STARTING FULL LIVE END-TO-END ACCEPTANCE TESTING ===")

# 1. Health
h = req("GET", "/health")
print(f"[1] GET /health -> Status: {h['status']} ({h['duration']}s), Data: {h['data']}")

# 2. Readiness
r = req("GET", "/ready")
print(f"[2] GET /ready -> Status: {r['status']} ({r['duration']}s), Status: {r['data'].get('status')}")

# 3. Create Session
s = req("POST", "/sessions", {})
session_id = s['data'].get('session_id')
print(f"[3] POST /sessions -> Status: {s['status']} ({s['duration']}s), Session ID: {session_id}")

# 4. Chat Query (Simple Question)
c1 = req("POST", "/chat", {
    "query": "What is BIS certification?",
    "session_id": session_id,
    "style": "simple"
})
print(f"[4] POST /chat (Simple) -> Status: {c1['status']} ({c1['duration']}s), Reply snippet: {c1['data'].get('reply', '')[:100]}...")

# 5. Chat Query (Short Style)
c2 = req("POST", "/chat", {
    "query": "Give me a quick 2-sentence overview of QCO.",
    "session_id": session_id,
    "style": "short"
})
if "data" in c2 and isinstance(c2["data"], dict):
    print(f"[5] POST /chat (Short) -> Status: {c2['status']} ({c2['duration']}s), Reply snippet: {c2['data'].get('reply', '')[:100]}...")
else:
    print(f"[5] POST /chat (Short) -> Status: {c2['status']} ({c2['duration']}s), Response: {c2.get('error') or c2}")

# 6. Upload Controlled Test PDF
pdf_content = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>/Contents 4 0 R>>endobj\n"
    b"4 0 obj<</Length 85>>stream\n"
    b"BT /F1 12 Tf 100 700 Td (TEST_BIS_ALPHA_7429 requires inspection every 37 days.) Tj ET\n"
    b"endstream\nendobj\n"
    b"xref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000101 00000 n\n0000000212 00000 n\n"
    b"trailer<</Size 5/Root 1 0 R>>\nstartxref\n348\n%%EOF"
)

boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
body = (
    f"--{boundary}\r\n"
    f'Content-Disposition: form-data; name="file"; filename="test_alpha.pdf"\r\n'
    f"Content-Type: application/pdf\r\n\r\n"
).encode("utf-8") + pdf_content + f"\r\n--{boundary}--\r\n".encode("utf-8")

u = req("POST", "/documents/upload", data=body, is_json=False, custom_headers={
    "Content-Type": f"multipart/form-data; boundary={boundary}"
})
doc_id = u['data'].get('document_id')
print(f"[6] POST /documents/upload -> Status: {u['status']} ({u['duration']}s), Doc ID: {doc_id}, Text Preview: {u['data'].get('extracted_text_preview')}")

# 7. Ask Chat with Attached Document
c3 = req("POST", "/chat", {
    "query": "What is the inspection interval for TEST_BIS_ALPHA_7429?",
    "session_id": session_id,
    "document_id": doc_id,
    "style": "simple"
})
print(f"[7] POST /chat (With Document ID {doc_id}) -> Status: {c3['status']} ({c3['duration']}s)")
print(f"    Answer: {c3['data'].get('reply')}")
print(f"    Sources: {json.dumps(c3['data'].get('sources'))}")

# 8. Delete Document
d = req("DELETE", f"/documents/{doc_id}")
print(f"[8] DELETE /documents/{doc_id} -> Status: {d['status']} ({d['duration']}s)")

# 9. Get Session Messages
m = req("GET", f"/sessions/{session_id}/messages")
print(f"[9] GET /sessions/{session_id}/messages -> Status: {m['status']} ({m['duration']}s), Total Messages: {len(m['data'])}")

# 10. Compliance Check
comp = req("POST", "/compliance/check", {
    "category": "Toys",
    "description": "Plastic toy action figure",
    "manufacturer_scale": "large",
    "is_imported": False
})
print(f"[10] POST /compliance/check -> Status: {comp['status']} ({comp['duration']}s), QCO ID: {comp['data'].get('qco_result', {}).get('qco_id')}")

# 11. Flashcard Generation
fc = req("POST", "/flashcards/generate", {
    "topic": "BIS certification for footwear",
    "num_cards": 3,
    "use_rag": False
})
print(f"[11] POST /flashcards/generate -> Status: {fc['status']} ({fc['duration']}s), Cards generated: {fc['data'].get('num_generated')}")

# 12. Delete Session
del_s = req("DELETE", f"/sessions/{session_id}")
print(f"[12] DELETE /sessions/{session_id} -> Status: {del_s['status']} ({del_s['duration']}s)")

print("=== LIVE E2E ACCEPTANCE SCRIPT COMPLETE ===")
