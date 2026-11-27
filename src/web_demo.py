"""Local cmt-tag demo. It uses only the frozen V2 training input."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from unicodedata import normalize
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen
import webbrowser

from scripts.chuan_hoa_binh_luan_v2 import normalize_v2
from src.models.core import LABELS, v2_baseline_model
from src.web_bert import APP_NAME, BERT_NAMES, RECEIPT, ModalBert, RemotePredictionError
from src.web_crawl import CrawlBusy, WebCrawl


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "web"
DEFAULT_TRAIN_DIR = ROOT / "outputs" / "03_Dau_vao_chinh_thuc"
T2_RESULTS_DIR = ROOT / "outputs" / "08_Danh_gia_T2_V2"
T2_THREE_SEED_RESULTS_DIR = ROOT / "outputs" / "08_Danh_gia_T2_V2_3_seed"
T2_ALL_MODELS_RESULTS_DIR = ROOT / "outputs" / "08_Danh_gia_T2_V2_6_mo_hinh_3_seed"
T2_DETAILED_RESULTS_DIR = ROOT / "outputs" / "08_Danh_gia_T2_V2_chi_tiet"
MODEL_NAMES = {
    "tfidf_word_svm": "TF-IDF từ + LinearSVC",
    "tfidf_char_svm": "TF-IDF ký tự + LinearSVC",
    "bow_complement_nb": "BoW + Complement NB",
    "bow_multinomial_nb": "BoW + Multinomial NB",
}
STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}
MAX_TEXT = 2000
MAX_BODY = 32768
COMMENT_PAGE_SIZE = 10


def read_train(train_dir):
    manifest = json.loads((train_dir / "manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("kind") not in {"V2_OFFICIAL_FROZEN_INPUTS", "V2_FINAL_CONSENSUS_TRAIN"}
            or manifest.get("input_view") != "normalize_v2"):
        raise ValueError("Cần snapshot V2 với đầu vào normalize_v2")
    train_path = train_dir / "train.local.jsonl"
    payload = train_path.read_bytes()
    fingerprint = sha256(payload).hexdigest()
    if fingerprint != manifest["output_sha256"][train_path.name]:
        raise ValueError("SHA-256 của file train lệch manifest")

    rows = [json.loads(line) for line in payload.decode("utf-8").splitlines() if line]
    counts = Counter(row["label"] for row in rows)
    if (set(counts) != set(LABELS) or counts != manifest["train_labels"]
            or len(rows) != manifest["train_size"]
            or len({row["id"] for row in rows}) != len(rows)
            or any(not isinstance(row["text"], str) or not row["text"].strip() for row in rows)):
        raise ValueError("Dữ liệu train lệch snapshot")
    dataset = {
        "train_size": len(rows), "train_labels": dict(counts), "train_sha256": fingerprint,
        "test_size": manifest.get("test_size"), "test_groups": manifest.get("test_groups", {}),
    }
    if manifest["kind"] == "V2_FINAL_CONSENSUS_TRAIN":
        locked_train = sum(row["origin"] in {"E", "C", "U"} for row in rows)
        dataset["consensus"] = {
            "annotated": manifest["ai_roster_size"],
            "agreed": manifest["strict_ai_consensus"],
            "locked": manifest["locked_ecu"],
            "identity_excluded": manifest["exclusions"].get("missing_post_or_shared_T2_identity", 0),
            "duplicate_excluded": sum(manifest["exclusions"].get(key, 0) for key in ("exact_T2_text", "near_T2_text")),
            "train_agreed": len(rows) - locked_train,
            "train_locked": locked_train,
        }
    return [row["text"] for row in rows], [row["label"] for row in rows], dataset


def read_t2_results(dataset, bert_receipt_sha256):
    if dataset is None or bert_receipt_sha256 is None:
        return None
    try:
        report = json.loads((T2_DETAILED_RESULTS_DIR / "manifest.json").read_text(encoding="utf-8"))
        if (report["kind"] != "V2_FINAL_T2_DETAILED_EVALUATION"
                or report["train_sha256"] != dataset["train_sha256"]
                or report["train_size"] != dataset["train_size"]
                or report["test_size"] != dataset["test_size"]
                or report["test_groups"] != dataset["test_groups"]
                or report["bert_receipt_sha256"] != bert_receipt_sha256):
            return None
        scores, deviations, seeds = report["scores"], report["std"], report["seeds"]
        matrices = report["confusion_matrices"]
        model_ids = MODEL_NAMES.keys() | BERT_NAMES.keys()
        if (scores.keys() != model_ids or deviations.keys() != model_ids or matrices.keys() != model_ids
                or report["labels"] != LABELS
                or report["std_definition"] != "sample_n_minus_1" or not isinstance(seeds, list)
                or any(type(seed) is not int for seed in seeds) or len(seeds) != 3 or len(set(seeds)) != 3
                or any(metrics.keys() != {"macro_f1", "accuracy", "macro_precision", "macro_recall"}
                       or any(type(value) not in (int, float) or not 0 <= value <= 1
                              for value in metrics.values()) for metrics in (*scores.values(), *deviations.values()))):
            raise ValueError("invalid T2 scores")
        for runs in matrices.values():
            if runs.keys() != {str(seed) for seed in seeds}:
                raise ValueError("missing T2 confusion matrix")
            for matrix in runs.values():
                if (len(matrix) != len(LABELS) or any(len(row) != len(LABELS) for row in matrix)
                        or any(type(count) is not int or count < 0 for row in matrix for count in row)
                        or sum(map(sum, matrix)) != dataset["test_size"]):
                    raise ValueError("invalid T2 confusion matrix")
        return {"scores": scores, "std": deviations, "seeds": seeds,
                "labels": LABELS, "confusion_matrices": matrices}
    except FileNotFoundError:
        return None
    except (AttributeError, KeyError, OSError, TypeError, ValueError) as exc:
        print(f"T2 scores could not be loaded: {exc!a}", flush=True)
        return None


class Demo:
    def __init__(self, train_dir, bert_receipt=RECEIPT):
        self.models = {}
        self.bert = {}
        self.dataset = None
        self.comments = ()
        self.crawl = WebCrawl(ROOT / "data/web_demo/crawl", ROOT / "data/browser_profile_brave_manual")
        self.load_error = None
        try:
            self.train(train_dir)
        except (OSError, ValueError, KeyError) as exc:
            self.load_error = "Cần snapshot train V2 đã khóa để bật dự đoán."
            print(f"Demo training input could not be loaded: {exc!a}", flush=True)
        receipt_sha256 = self.load_bert(bert_receipt) if self.dataset is not None else None
        self.t2_results = read_t2_results(self.dataset, receipt_sha256)

    def load_bert(self, path):
        if not path.is_file():
            return None
        try:
            payload = path.read_bytes()
            receipt = json.loads(payload)
            if receipt.get("app") != APP_NAME:
                raise ValueError("unexpected app name")
            for entry in receipt["models"]:
                self.bert[entry["model"]] = ModalBert(entry, self.dataset["train_sha256"])
        except (OSError, ImportError, KeyError, ValueError) as exc:
            print(f"Demo BERT configuration could not be loaded: {exc!a}", flush=True)
            return None
        return sha256(payload).hexdigest()

    def train(self, train_dir):
        texts, labels, dataset = read_train(train_dir)
        models = {}
        for key in MODEL_NAMES:
            models[key] = v2_baseline_model(key).fit(texts, labels)
            print(f"Loaded demo baseline: {key}", flush=True)
        self.models = models
        self.dataset = dataset
        self.comments = tuple(zip(texts, labels, strict=True))

    def list_comments(self, query):
        params = parse_qs(query, max_num_fields=10)
        label = params.get("label", [""])[0]
        search = normalize("NFC", params.get("q", [""])[0].strip()).casefold()
        page = int(params.get("page", ["1"])[0])
        if len(search) > 200 or page < 1 or (label and label not in LABELS):
            raise ValueError("Bộ lọc hoặc số trang không hợp lệ.")
        matching = [
            (text, value) for text, value in self.comments
            if (not label or value == label) and (not search or search in text.casefold())
        ]
        total = len(matching)
        pages = max(1, (total + COMMENT_PAGE_SIZE - 1) // COMMENT_PAGE_SIZE)
        page = min(page, pages)
        start = (page - 1) * COMMENT_PAGE_SIZE
        return {
            "page": page, "pages": pages, "total": total, "offset": start,
            "comments": [{"text": text, "label": value}
                         for text, value in matching[start:start + COMMENT_PAGE_SIZE]],
        }

    def status(self):
        return {
            "app": "cmt-tag",
            "models": [
                {"id": key, "name": name, "provider": "local"}
                for key, name in MODEL_NAMES.items() if key in self.models
            ] + [
                {"id": key, "name": name, "provider": "modal"}
                for key, name in BERT_NAMES.items() if key in self.bert
            ],
            "dataset": self.dataset,
            "t2_results": self.t2_results,
            "message": self.load_error,
        }

    def analyze(self, payload):
        if not isinstance(payload, dict) or not isinstance(payload.get("text"), str):
            raise ValueError("Hãy nhập bình luận dạng văn bản.")
        raw = payload["text"]
        if len(raw) > MAX_TEXT:
            raise ValueError(f"Bình luận tối đa {MAX_TEXT} ký tự.")
        normalized = normalize_v2(raw)
        if not normalized:
            raise ValueError("Hãy nhập một bình luận để phân tích.")
        model_id = payload.get("model")
        result = {"normalized": normalized, "changed": raw != normalized}
        if model_id is None:
            return result
        if not isinstance(model_id, str):
            raise ValueError("Mô hình này chưa sẵn sàng.")
        if model_id in self.bert:
            predicted = self.bert[model_id].predict(normalized)
            return {
                **result, "label": predicted["label"], "model": BERT_NAMES[model_id],
                "score_kind": "softmax", "scores": predicted["scores"], "provider": "modal",
            }
        if model_id not in self.models:
            raise ValueError("Mô hình này chưa sẵn sàng.")
        model = self.models[model_id]
        values = [normalized]
        if hasattr(model, "predict_proba"):
            scores, kind = model.predict_proba(values)[0], "probability"
        else:
            scores, kind = model.decision_function(values)[0], "margin"
        return {
            **result,
            "label": str(model.predict(values)[0]),
            "model": MODEL_NAMES[model_id],
            "provider": "local",
            "score_kind": kind,
            "scores": {str(label): float(score) for label, score in zip(model.classes_, scores, strict=True)},
        }

    def label_crawl(self, payload):
        model_id = payload.get("model") if isinstance(payload, dict) else None
        if not isinstance(model_id, str) or (model_id not in self.models and model_id not in self.bert):
            raise ValueError("Hãy chọn một mô hình đang sẵn sàng.")
        job = self.crawl.status()
        if not job or payload.get("id") != job["id"] or "comments" not in job:
            raise CrawlBusy("Hãy chờ lượt crawl hiện tại kết thúc.")
        comments = job["comments"]
        texts = [(i, normalized) for i, row in enumerate(comments)
                 if (normalized := normalize_v2(row["text"]))]
        labels = {}
        is_bert = model_id in self.bert
        if texts:
            indices, phrases = zip(*texts, strict=True)
            if is_bert:
                predictions = [row["label"] for row in self.bert[model_id].predict_batch(phrases)]
            else:
                predictions = self.models[model_id].predict(phrases)
            labels = dict(zip(indices, predictions, strict=True))
        return {
            "id": job["id"], "model": (BERT_NAMES if is_bert else MODEL_NAMES)[model_id],
            "provider": "modal" if is_bert else "local",
            "comments": [{**row, "label": str(labels[i]) if i in labels else None}
                         for i, row in enumerate(comments)],
        }


class Handler(BaseHTTPRequestHandler):
    def __init__(self, *args, demo, **kwargs):
        self.demo = demo
        super().__init__(*args, **kwargs)

    def respond(self, status, content, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(content)

    def json_reply(self, status, data):
        self.respond(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def local_request(self):
        port = self.server.server_port
        hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        origin = self.headers.get("Origin")
        return self.headers.get("Host") in hosts and (origin is None or origin in {f"http://{host}" for host in hosts})

    def do_GET(self):
        target = urlsplit(self.path)
        route = target.path
        if route in {"/api/comments", "/api/crawl"} and not self.local_request():
            self.json_reply(HTTPStatus.FORBIDDEN, {"error": "Chỉ truy cập từ web demo trên máy này."})
            return
        if route == "/api/status":
            self.json_reply(HTTPStatus.OK, self.demo.status())
        elif route == "/api/comments":
            if self.demo.dataset is None:
                self.json_reply(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "Chưa có snapshot train V2."})
                return
            try:
                self.json_reply(HTTPStatus.OK, self.demo.list_comments(target.query))
            except ValueError:
                self.json_reply(HTTPStatus.BAD_REQUEST, {"error": "Bộ lọc hoặc số trang không hợp lệ."})
        elif route == "/api/crawl":
            self.json_reply(HTTPStatus.OK, self.demo.crawl.status())
        elif route in STATIC:
            leaf, content_type = STATIC[route]
            self.respond(HTTPStatus.OK, (ASSETS / leaf).read_bytes(), content_type)
        else:
            self.json_reply(HTTPStatus.NOT_FOUND, {"error": "Trang không tồn tại."})

    def do_POST(self):
        if self.path not in {"/api/analyze", "/api/crawl", "/api/crawl/continue", "/api/crawl/labels"}:
            self.json_reply(HTTPStatus.NOT_FOUND, {"error": "Trang không tồn tại."})
            return
        if self.path != "/api/analyze" and not self.local_request():
            self.json_reply(HTTPStatus.FORBIDDEN, {"error": "Chỉ truy cập từ web demo trên máy này."})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= MAX_BODY or self.headers.get_content_type() != "application/json":
                raise ValueError("Dữ liệu gửi lên không hợp lệ.")
            try:
                payload = json.loads(self.rfile.read(length))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise ValueError("Dữ liệu gửi lên không phải JSON hợp lệ.") from None
            if self.path == "/api/crawl":
                self.json_reply(HTTPStatus.ACCEPTED, self.demo.crawl.start(payload))
            elif self.path == "/api/crawl/continue":
                self.json_reply(HTTPStatus.OK, self.demo.crawl.resume(payload))
            elif self.path == "/api/crawl/labels":
                self.json_reply(HTTPStatus.OK, self.demo.label_crawl(payload))
            else:
                self.json_reply(HTTPStatus.OK, self.demo.analyze(payload))
        except CrawlBusy as exc:
            self.json_reply(HTTPStatus.CONFLICT, {"error": str(exc)})
        except OSError:
            self.json_reply(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "Không ghi được dữ liệu cục bộ."})
        except RemotePredictionError as exc:
            self.json_reply(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc)})
        except ValueError as exc:
            self.json_reply(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

    def log_message(self, _format, *_args):
        """Keep pasted comments and request details out of terminal history."""


def main():
    parser = argparse.ArgumentParser(description="Chạy demo phân tích cảm xúc cmt-tag cục bộ.")
    parser.add_argument("--train-dir", type=Path, default=DEFAULT_TRAIN_DIR)
    parser.add_argument("--bert-receipt", type=Path, default=RECEIPT)
    parser.add_argument("--port", type=int, default=8768)
    parser.add_argument("--open", action="store_true", help="Mở trình duyệt sau khi demo khởi động.")
    args = parser.parse_args()
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    except OSError:
        url = f"http://127.0.0.1:{args.port}/"
        if args.open and existing_demo(url):
            webbrowser.open(url)
            return
        raise
    with server:
        server.RequestHandlerClass = partial(Handler, demo=Demo(args.train_dir, args.bert_receipt))
        url = f"http://127.0.0.1:{server.server_port}/"
        print(f"cmt-tag demo: {url}", flush=True)
        if args.open:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


def existing_demo(url):
    try:
        with urlopen(url + "api/status", timeout=1) as response:
            return json.load(response).get("app") == "cmt-tag"
    except (OSError, ValueError):
        return False


if __name__ == "__main__":
    main()
