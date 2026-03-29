from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from google_auth_oauthlib.flow import Flow
import os
import requests

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"  # local testing only

CLIENT_SECRET_FILE = "client_secret.json"
SCOPES = ["https://www.googleapis.com/auth/documents",  # need write access
          "https://www.googleapis.com/auth/drive"]      # if you want folder move etc
REDIRECT_URI = "http://localhost:8000/auth/callback"

app = FastAPI()

flow = Flow.from_client_secrets_file(
    CLIENT_SECRET_FILE,
    scopes=SCOPES,
    redirect_uri=REDIRECT_URI
)

@app.get("/auth")
def auth():
    auth_url, _ = flow.authorization_url(prompt="consent")
    return RedirectResponse(auth_url)

@app.get("/auth/callback")
def auth_callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Missing code parameter")
    flow.fetch_token(code=code)
    credentials = flow.credentials
    return JSONResponse({
        "access_token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "expires_in": credentials.expiry.isoformat()
    })

@app.post("/document/create-and-insert")
def create_and_insert(token: str, title: str = "My New Doc", text: str = "Hello world!"):
    # 1) Create the doc
    url_create = "https://docs.googleapis.com/v1/documents"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body_create = {"title": title}
    r1 = requests.post(url_create, headers=headers, json=body_create)
    if r1.status_code != 200:
        raise HTTPException(status_code=r1.status_code, detail=f"Error creating doc: {r1.text}")
    doc = r1.json()
    doc_id = doc.get("documentId")
    if not doc_id:
        raise HTTPException(status_code=500, detail="No documentId in create response")

    # 2) Insert text into the doc
    url_batch = f"https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate"
    # use endOfSegmentLocation to append text at end (rather than a fixed index)
    requests_body = {
        "requests": [
            {
                "insertText": {
                    "endOfSegmentLocation": {},
                    "text": text
                }
            }
        ]
    }
    r2 = requests.post(url_batch, headers=headers, json=requests_body)
    if r2.status_code != 200:
        raise HTTPException(status_code=r2.status_code, detail=f"Error inserting text: {r2.text}")

    return JSONResponse({
        "documentId": doc_id,
        "title": title,
        "insertedText": text
    })

@app.post("/document/{doc_id}/insert-text")
def insert_text(doc_id: str, token: str, text: str):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url_batch = f"https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate"
    requests_body = {
        "requests": [
            {
                "insertText": {
                    "endOfSegmentLocation": {},
                    "text": text
                }
            }
        ]
    }
    r = requests.post(url_batch, headers=headers, json=requests_body)
    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail=f"Error inserting text: {r.text}")
    return JSONResponse({
        "documentId": doc_id,
        "insertedText": text
    })
