from __future__ import annotations

import logging
from dataclasses import dataclass
import time

from ..ascii import AsciiConverter
from ..capture import ScreenCaptureBackend
from ..control import ActionExecutor, ExecutedAction
from ..profiles import GameProfile
from .runtime import PolicyRuntime

logger = logging.getLogger(__name__)


@dataclass
class LivePolicyConfig:
    fps: float = 5.0
    duration_s: float | None = None
    print_actions: bool = False


class LivePolicyRunner:
    def __init__(
        self,
        runtime: PolicyRuntime,
        capture_backend: ScreenCaptureBackend,
        profile: GameProfile,
        ascii_converter: AsciiConverter,
        action_executor: ActionExecutor,
        config: LivePolicyConfig,
    ) -> None:
        self.runtime = runtime
        self.capture_backend = capture_backend
        self.profile = profile
        self.ascii_converter = ascii_converter
        self.action_executor = action_executor
        self.config = config

    def run(self) -> int:
        interval_s = 1.0 / self.config.fps
        executed = 0
        start_time = time.monotonic()
        next_tick = start_time
        try:
            while True:
                now = time.monotonic()
                if self.config.duration_s is not None and now - start_time >= self.config.duration_s:
                    break
                if now < next_tick:
                    time.sleep(next_tick - now)
                try:
                    captured = self.capture_backend.capture()
                except Exception as exc:
                    logger.warning("Capture failed, skipping frame: %s", exc)
                    next_tick += interval_s
                    continue
                ascii_text = self.ascii_converter.convert_simple(captured.grayscale)
                action_name, logits = self.runtime.predict(ascii_text)
                result = self.action_executor.apply(action_name, capture_region=captured.region)
                executed += 1
                if self.config.print_actions:
                    confidence = float(logits.softmax(dim=-1).max().item())
                    self._log_action(result, confidence)
                next_tick += interval_s
        finally:
            self.action_executor.close()
        return executed

    @staticmethod
    def _log_action(result: ExecutedAction, confidence: float) -> None:
        suffix_parts = []
        if result.held_keys:
            suffix_parts.append(f"keys={','.join(result.held_keys)}")
        if result.tapped_keys:
            suffix_parts.append(f"taps={','.join(result.tapped_keys)}")
        if result.clicked_buttons:
            suffix_parts.append(f"buttons={','.join(result.clicked_buttons)}")
        if result.pointer_target is not None:
            suffix_parts.append(f"pointer={result.pointer_target[0]},{result.pointer_target[1]}")
        suffix = f" ({'; '.join(suffix_parts)})" if suffix_parts else ""
        logger.info("%s confidence=%.2f%%%s", result.action_name, confidence * 100, suffix)
