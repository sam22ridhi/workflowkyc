"""The two deployment layers: the database URL (SQLite by default, Postgres/Supabase when asked) and the file storage (local disk, written through to Supabase Storage)."""
import httpx
import pytest

from app import config, db, storage


# ---------------------------------------------------------------- database URL
@pytest.mark.parametrize("raw,expected", [
    ("postgres://u:p@aws-0-ap.pooler.supabase.com:6543/postgres", "postgresql+psycopg://u:p@aws-0-ap.pooler.supabase.com:6543/postgres?sslmode=require"),
    ("postgresql://u:p@db.abc.supabase.co:5432/postgres", "postgresql+psycopg://u:p@db.abc.supabase.co:5432/postgres?sslmode=require"),
    ("postgresql://u:p@host/db?application_name=x", "postgresql+psycopg://u:p@host/db?application_name=x&sslmode=require"),
    ("postgresql+psycopg://u:p@host/db?sslmode=disable", "postgresql+psycopg://u:p@host/db?sslmode=disable"),
    ("postgresql://u:p@localhost:5432/db", "postgresql+psycopg://u:p@localhost:5432/db"),               # local Postgres needs no SSL
])
def test_database_url_is_normalised_for_psycopg_and_supabase_ssl(raw, expected):
    assert db.normalise_database_url(raw) == expected


def test_the_default_is_sqlite_and_a_url_switches_to_postgres(monkeypatch):
    monkeypatch.setattr(config, "DATABASE_URL", "")
    assert db.is_postgres() is False and db.make_engine().dialect.name == "sqlite"
    monkeypatch.setattr(config, "DATABASE_URL", "postgresql://u:p@localhost:5432/x")
    assert db.is_postgres() is True and db.make_engine().dialect.name == "postgresql"


# ---------------------------------------------------------------- file storage
class FakeBucket:
    """Stands in for Supabase Storage's REST API: upload (POST object), download (GET object), delete (DELETE object), list (POST object/list)."""

    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.calls: list[tuple[str, str]] = []

    def install(self, monkeypatch):
        base = f"{config.SUPABASE_URL}/storage/v1/object/"
        bucket = config.SUPABASE_BUCKET

        def key(url: str) -> str:
            from urllib.parse import unquote
            return unquote(url.split(f"/object/{bucket}/", 1)[1])

        def post(url, content=None, json=None, headers=None, timeout=None):
            self.calls.append(("POST", url))
            assert headers["Authorization"].startswith("Bearer ") and headers["apikey"]
            if "/object/list/" in url:
                prefix = json["prefix"]
                names, seen = [], set()
                for k in self.objects:
                    if k.startswith(prefix + "/"):
                        rest = k[len(prefix) + 1:]
                        head = rest.split("/")[0]
                        if "/" in rest and head not in seen:
                            seen.add(head)
                            names.append({"name": head, "id": None})
                        elif "/" not in rest:
                            names.append({"name": rest, "id": "x"})
                return httpx.Response(200, json=names, request=httpx.Request("POST", url))
            self.objects[key(url)] = content
            return httpx.Response(200, json={"Key": key(url)}, request=httpx.Request("POST", url))

        def get(url, headers=None, timeout=None):
            self.calls.append(("GET", url))
            k = key(url)
            if k not in self.objects:
                return httpx.Response(404, json={"error": "not found"}, request=httpx.Request("GET", url))
            return httpx.Response(200, content=self.objects[k], request=httpx.Request("GET", url))

        def request(method, url, json=None, headers=None, timeout=None):
            self.calls.append((method, url))
            for k in json["prefixes"]:
                self.objects.pop(k, None)
            return httpx.Response(200, json=[], request=httpx.Request(method, url))

        monkeypatch.setattr(httpx, "post", post)
        monkeypatch.setattr(httpx, "get", get)
        monkeypatch.setattr(httpx, "request", request)
        assert base


@pytest.fixture
def bucket(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "STORAGE_DIR", tmp_path / "storage")
    (tmp_path / "storage").mkdir()
    monkeypatch.setattr(config, "SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setattr(config, "SUPABASE_SERVICE_KEY", "service-key")
    monkeypatch.setattr(config, "SUPABASE_BUCKET", "karyakarta-files")
    fb = FakeBucket()
    fb.install(monkeypatch)
    return fb


def make(tmp, case="KYB-1", name="doc1_GST certificate (final).pdf", data=b"%PDF-1.4 hello"):
    p = tmp / "storage" / case / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p


def test_nothing_configured_is_plain_local_disk(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "STORAGE_DIR", tmp_path / "storage")
    monkeypatch.setattr(config, "SUPABASE_URL", "")
    monkeypatch.setattr(config, "SUPABASE_SERVICE_KEY", "")
    p = make(tmp_path)
    assert storage.configured() is False and storage.save_remote(p) is True and storage.ensure_local(p) == p
    p.unlink()
    with pytest.raises(FileNotFoundError, match="no file storage is configured"):
        storage.ensure_local(p)


def test_keys_are_safe_and_relative(bucket, tmp_path):
    p = make(tmp_path, name="doc1_GST certificate (final).pdf")
    assert storage.key_for(p) == "KYB-1/doc1_GST_certificate__final_.pdf"
    assert storage.key_for(make(tmp_path, name="a_b.jpg", case="KYB-2")) == "KYB-2/a_b.jpg"


def test_a_file_is_written_through_and_restored_after_the_local_copy_is_lost(bucket, tmp_path):
    p = make(tmp_path)
    assert storage.save_remote(p) is True
    assert bucket.objects[storage.key_for(p)] == b"%PDF-1.4 hello"
    p.unlink()                                                    # a restart or redeploy of a server with a temporary disk
    again = storage.ensure_local(p)
    assert again == p and p.read_bytes() == b"%PDF-1.4 hello"


def test_a_failed_write_through_never_breaks_the_upload(monkeypatch, bucket, tmp_path):
    p = make(tmp_path)
    monkeypatch.setattr(httpx, "post", lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("down")))
    assert storage.save_remote(p) is False and p.exists()


def test_a_file_that_cannot_be_restored_is_reported(bucket, tmp_path):
    p = tmp_path / "storage" / "KYB-1" / "ghost.pdf"
    with pytest.raises(FileNotFoundError, match="could not be restored"):
        storage.ensure_local(p)


def test_delete_removes_both_copies(bucket, tmp_path):
    p = make(tmp_path)
    storage.save_remote(p)
    storage.delete(p)
    assert not p.exists() and storage.key_for(p) not in bucket.objects


def test_delete_prefix_removes_a_whole_case_including_sub_folders(bucket, tmp_path):
    a, b = make(tmp_path, name="d1_a.pdf"), make(tmp_path, name="cpv/s1_exterior.jpg", data=b"jpg")
    other = make(tmp_path, case="KYB-2", name="keep.pdf")
    for f in (a, b, other):
        storage.save_remote(f)
    storage.delete_prefix(tmp_path / "storage" / "KYB-1")
    assert not (tmp_path / "storage" / "KYB-1").exists()
    assert set(bucket.objects) == {"KYB-2/keep.pdf"} and other.exists()


def test_paths_outside_the_storage_folder_are_never_deleted(bucket, tmp_path):
    outside = tmp_path / "precious.txt"
    outside.write_text("keep me")
    storage.delete(outside)
    storage.delete_prefix(tmp_path)
    assert outside.exists()
