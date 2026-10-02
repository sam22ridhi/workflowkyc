# Karyakarta backend: step 1 (PAN extraction)

Flow: React/curl -> FastAPI `/documents/upload` -> n8n webhook -> n8n calls FastAPI `/documents/{id}/extract`
-> FastAPI calls Sarvam Document Intelligence (extract) -> rule checks in Python -> SQLite -> back to n8n.

## 1. Setup
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # put your SARVAM_API_KEY in it
python scripts/make_sample_pan.py                      # creates samples/pan_sharma_foods.png
```

## 2. Test Sarvam alone
```bash
python scripts/test_sarvam_pan.py samples/pan_sharma_foods.png
python scripts/test_sarvam_pan.py samples/pan_bad_type.png   # should FAIL holder type + name
```

## 3. Run FastAPI
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# docs at http://localhost:8000/docs
```

## 4. Run n8n (Docker)
```bash
docker run -it --rm --name n8n -p 5678:5678 \
  --add-host=host.docker.internal:host-gateway \
  -v n8n_data:/home/node/.n8n docker.n8n.io/n8nio/n8n
```
Inside n8n, FastAPI is at `http://host.docker.internal:8000` (not localhost).

## 5. End-to-end
```bash
curl -F "file=@samples/pan_sharma_foods.png" -F doc_type=pan \
     -F declared_entity_type=private_limited -F "declared_name=Sharma Foods Private Limited" \
     http://localhost:8000/documents/upload
curl http://localhost:8000/documents/<doc_id>
```
