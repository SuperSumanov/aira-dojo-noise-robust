"""HTTP service for scoring MLE-bench code with a Bradley--Terry reward model."""
from __future__ import annotations

import argparse
import json
import os
import queue
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import torch

from .bradley_terry_evaluation import _score_sequences, load_checkpoint


class RewardScorer:
    """Tokenize and score one task/code request."""

    def __init__(self, checkpoint: str, base_model: str | None = None):
        self.model, self.tokenizer, self.meta = load_checkpoint(
            checkpoint, base_model=base_model, device_map="auto"
        )
        self.max_len = int(self.meta.get("max_len", 16384))
        self.head_frac = float(self.meta.get("head_frac", 0.25))
        self.task_cond = bool(self.meta.get("task_cond", True))

    def _truncate(self, ids: list[int]) -> list[int]:
        if len(ids) <= self.max_len:
            return ids
        head = int(self.max_len * self.head_frac)
        return ids[:head] + ids[-(self.max_len - head) :]

    def encode(self, task: str, code: str) -> list[int]:
        prefix = f"# MLE-bench task: {task}\n" if self.task_cond else ""
        return self._truncate(self.tokenizer(prefix + code, add_special_tokens=False)["input_ids"])

    @torch.no_grad()
    def score_batch(self, requests: list[tuple[str, str]]) -> list[float]:
        ids = [self.encode(task, code) for task, code in requests]
        logits = _score_sequences(self.model, ids, self.tokenizer.pad_token_id)
        return [float(torch.sigmoid(torch.tensor(logit)).item()) for logit in logits]


@dataclass
class PendingRequest:
    task: str
    code: str
    done: threading.Event
    score: float | None = None
    error: Exception | None = None


class BatchScoringQueue:
    """Serialize model calls and process up to ``batch_size`` requests at once."""

    def __init__(self, scorer: RewardScorer, batch_size: int):
        self.scorer = scorer
        self.batch_size = batch_size
        self.requests: queue.Queue[PendingRequest] = queue.Queue()
        self.worker = threading.Thread(target=self._run, name="rm-batch-worker", daemon=True)
        self.worker.start()

    def submit(self, task: str, code: str) -> float:
        request = PendingRequest(task, code, threading.Event())
        self.requests.put(request)
        request.done.wait()
        if request.error is not None:
            raise request.error
        assert request.score is not None
        return request.score

    def _run(self) -> None:
        while True:
            batch = [self.requests.get()]
            # Give requests already arriving in the same burst a short window
            # to join the batch, without adding noticeable latency when idle.
            deadline = time.monotonic() + 0.01
            while len(batch) < self.batch_size:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    batch.append(self.requests.get(timeout=remaining))
                except queue.Empty:
                    break
            try:
                scores = self.scorer.score_batch([(r.task, r.code) for r in batch])
                for request, score in zip(batch, scores):
                    request.score = score
            except Exception as exc:
                for request in batch:
                    request.error = exc
            finally:
                for request in batch:
                    request.done.set()


def make_handler(batch_queue: BatchScoringQueue):
    class ScoreHandler(BaseHTTPRequestHandler):
        def log_message(self, *_args: Any) -> None:
            return

        def do_POST(self) -> None:  # noqa: N802 (stdlib API name)
            try:
                if self.path != "/score":
                    self._respond(404, {"error": "not found"})
                    return
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length))
                value = batch_queue.submit(str(payload.get("task", "")), str(payload.get("code", "")))
                self._respond(200, {"score": value})
            except Exception as exc:
                self._respond(500, {"error": str(exc)[:200]})

        def _respond(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return ScoreHandler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", default=os.environ.get("RM_DIR"))
    parser.add_argument("--base-model", default=os.environ.get("RM_BASE_MODEL"))
    parser.add_argument("--host", default=os.environ.get("RM_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("RM_PORT", "8765")))
    parser.add_argument("--batch-size", type=int, default=int(os.environ.get("RM_BATCH_SIZE", "1")),
                        help="maximum number of requests in one model forward pass")
    args = parser.parse_args()
    if not args.checkpoint:
        parser.error("--checkpoint or RM_DIR is required")
    if args.batch_size < 1:
        parser.error("--batch-size must be positive")
    scorer = RewardScorer(args.checkpoint, args.base_model)
    batch_queue = BatchScoringQueue(scorer, args.batch_size)
    print(f"[rm_server] loaded {args.checkpoint} (max_len={scorer.max_len}, task_cond={scorer.task_cond}, batch_size={args.batch_size})", flush=True)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(batch_queue))
    print(f"[rm_server] listening on {args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
