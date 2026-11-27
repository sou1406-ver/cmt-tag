"""Run the existing Facebook collector for one post from the local demo."""

import json
from pathlib import Path
import re
from threading import Event, Lock, Thread

from src.crawler.__main__ import browser_options, browser_page
from src.crawler.browser import run_posts
from src.crawler.parser import facebook_url, post_id
from src.crawler.store import Store, load_lines, write_json


CRAWL_LIMIT = 200
LOGIN_WAIT_SECONDS = 300
BUSY_PHASES = {"opening", "waiting", "collecting"}
FINISH_MESSAGES = {
    "access_barrier": "Facebook yêu cầu đăng nhập, xác minh hoặc quyền truy cập bài. Hãy kiểm tra trong Brave rồi chạy lại.",
    "comment_limit": "Đã thu đến giới hạn đã chọn.",
    "visible_dom_exhausted": "Đã đọc hết phần bình luận tải được trong phiên này.",
    "no_recognized_comments": "Crawler chưa nhận diện được bình luận trên bài này.",
}


class CrawlBusy(RuntimeError):
    pass


class WebCrawl:
    def __init__(self, root, profile):
        self.root = Path(root)
        self.profile = Path(profile)
        self.job_file = self.root / "latest.json"
        self.lock = Lock()
        self.worker = None
        self.ready = None
        self.job = self.read_last_job()

    def read_last_job(self):
        try:
            job = json.loads(self.job_file.read_text(encoding="utf-8"))
            if not re.fullmatch(r"fb_[0-9a-f]{32}", job["id"]):
                return None
            phase = job["phase"]
        except (OSError, ValueError, TypeError, KeyError):
            return None
        if phase in BUSY_PHASES:
            return {**job, "phase": "stopped", "message": "Phiên crawl trước đã dừng khi web đóng."}
        return job

    def set_phase(self, phase, message):
        self.job = {**self.job, "phase": phase, "message": message}
        write_json(self.job_file, self.job)

    def start(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("Cần link bài Facebook và mã phim.")
        url = payload.get("url")
        if not isinstance(url, str) or len(url) > 2000:
            raise ValueError("Hãy nhập link bài Facebook.")
        try:
            url = facebook_url(url.strip())
            if not post_id(url):
                raise ValueError()
        except ValueError:
            raise ValueError("Hãy nhập link trực tiếp của bài Facebook, dạng bài đăng, permalink hoặc video.") from None
        movie = payload.get("movie")
        if not isinstance(movie, str) or not re.fullmatch(r"[\w-]{1,60}", movie.strip()):
            raise ValueError("Mã phim dài 1–60 ký tự, dùng chữ, số, dấu gạch hoặc gạch dưới.")
        limit = payload.get("limit")
        if type(limit) is not int or not 1 <= limit <= CRAWL_LIMIT:
            raise ValueError(f"Giới hạn phải là số từ 1 đến {CRAWL_LIMIT}.")
        with self.lock:
            if self.worker and self.worker.is_alive():
                raise CrawlBusy("Đang có một lượt crawl. Hãy chờ lượt đó kết thúc.")
            launch = browser_options("brave")
            config = {
                "posts": [{"post_url": url, "movie_id": movie.strip()}],
                "max_posts": 1, "max_comments": limit, "post_timeout": 120,
                "max_rounds": 30, "max_actions": 12, "wait_ms": 12000, "settle_ms": 1500,
                "idle_rounds": 3, "retries": 0,
            }
            store = Store(self.root / "crawl_runs", config)
            self.ready = Event()
            self.job = {"id": store.run_id, "movie": movie.strip()}
            self.set_phase("opening", "Đang mở Brave với profile crawler.")
            self.worker = Thread(target=self.run, args=(store, launch, self.ready), daemon=True)
            self.worker.start()
            return self.job.copy()

    def resume(self, payload):
        with self.lock:
            if (not self.job or self.job["phase"] != "waiting" or not isinstance(payload, dict)
                    or payload.get("id") != self.job["id"]):
                raise CrawlBusy("Không có lượt crawl đang chờ đăng nhập.")
            self.set_phase("collecting", "Đang đọc bình luận từ bài Facebook.")
            self.ready.set()
            return self.job.copy()

    def run(self, store, launch, ready):
        try:
            with browser_page(self.profile, launch) as browser:
                with self.lock:
                    self.set_phase("waiting", "Đăng nhập Facebook trong Brave nếu cần, rồi bấm Tiếp tục crawl ở đây.")
                if ready.wait(LOGIN_WAIT_SECONDS):
                    run_posts(store, browser)
                    result = store.posts[-1]
                    reason = result["reason"]
                    phase = "blocked" if result["status"] == "blocked" else "finished"
                    message = FINISH_MESSAGES.get(reason, f"Đã dừng thu thập ({reason}).")
                else:
                    store.checkpoint("interrupted")
                    phase, message = "stopped", "Hết thời gian chờ xác nhận đăng nhập. Mở lượt crawl mới để thử lại."
        except Exception as exc:
            # Browser exceptions may contain URLs, page text or session details.
            print(f"Web crawl failed: {type(exc).__name__}", flush=True)
            try:
                store.checkpoint("interrupted")
            except OSError as error:
                print(f"Could not update crawl checkpoint: {type(error).__name__}", flush=True)
            phase, message = "failed", "Không chạy được crawler Brave. Kiểm tra Brave và đóng cửa sổ khác dùng cùng profile crawler."
        with self.lock:
            self.set_phase(phase, message)

    def status(self):
        with self.lock:
            job = self.job.copy() if self.job else None
        if job is None or job["phase"] in BUSY_PHASES:
            return job
        try:
            rows = load_lines(self.root / "crawl_runs" / job["id"] / "raw_comments.jsonl")
        except (OSError, ValueError):
            rows = []
        comments = [
            {"text": row["text_clean"], "kind": row["record_type"]}
            for row in rows
            if row.get("extraction_status") == "complete" and row.get("text_clean", "").strip()
        ]
        return {**job, "collected": len(rows), "comments": comments}
