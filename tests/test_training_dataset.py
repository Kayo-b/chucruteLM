from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from chucrutelm.profiles import build_tibia_profile
from chucrutelm.training import recorded_action_names, recorded_button_presses, summarize_recording


class RecordedActionNamesTest(unittest.TestCase):
    def test_returns_observed_actions_in_preferred_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.jsonl"
            manifest_path.write_text(
                "\n".join(
                    [
                        '{"action":{"action_name":"move_left"},"observation":{"ascii_text":"","numeric_features":{},"timestamp":0,"grid_width":80,"grid_height":60,"raw_inputs":{},"frame_path":null}}',
                        '{"action":{"action_name":"noop"},"observation":{"ascii_text":"","numeric_features":{},"timestamp":0,"grid_width":80,"grid_height":60,"raw_inputs":{},"frame_path":null}}',
                        '{"action":{"action_name":"move_right"},"observation":{"ascii_text":"","numeric_features":{},"timestamp":0,"grid_width":80,"grid_height":60,"raw_inputs":{},"frame_path":null}}',
                    ]
                ),
                encoding="utf-8",
            )

            action_names = recorded_action_names(
                manifest_path,
                preferred_order=["noop", "move_up", "move_down", "move_left", "move_right"],
            )

        self.assertEqual(action_names, ["noop", "move_left", "move_right"])

    def test_repairs_numeric_mouse_button_codes_via_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.jsonl"
            manifest_path.write_text(
                "\n".join(
                    [
                        '{"action":{"action_name":"noop","pressed_buttons":["272"],"pressed_keys":[],"source":"keyboard_mouse","tapped_buttons":["272"],"tapped_keys":[]},"observation":{"ascii_text":"","numeric_features":{},"timestamp":1.0,"grid_width":80,"grid_height":60,"raw_inputs":{"pressed_buttons":["272"],"pressed_keys":[],"tapped_buttons":["272"],"tapped_keys":[]},"frame_path":null}}',
                        '{"action":{"action_name":"noop","pressed_buttons":["273"],"pressed_keys":[],"source":"keyboard_mouse","tapped_buttons":["273"],"tapped_keys":[]},"observation":{"ascii_text":"","numeric_features":{},"timestamp":2.0,"grid_width":80,"grid_height":60,"raw_inputs":{"pressed_buttons":["273"],"pressed_keys":[],"tapped_buttons":["273"],"tapped_keys":[]},"frame_path":null}}',
                    ]
                ),
                encoding="utf-8",
            )

            profile = build_tibia_profile(action_names=["noop", "attack_interact", "context_use"])
            action_names = recorded_action_names(
                manifest_path,
                preferred_order=["noop", "attack_interact", "context_use"],
                profile=profile,
            )
            summary = summarize_recording(manifest_path, profile=profile)
            rows = recorded_button_presses(manifest_path, profile=profile)

        self.assertEqual(action_names, ["attack_interact", "context_use"])
        self.assertEqual(summary.action_counts["attack_interact"], 1)
        self.assertEqual(summary.action_counts["context_use"], 1)
        self.assertEqual(summary.pressed_button_counts, {"left": 1, "right": 1})
        self.assertEqual(summary.tapped_button_counts, {"left": 1, "right": 1})
        self.assertEqual(summary.button_action_counts, {"attack_interact": 1, "context_use": 1})
        self.assertEqual(rows[0].pressed_buttons, ("left",))
        self.assertEqual(rows[0].action_name, "attack_interact")
        self.assertEqual(rows[1].pressed_buttons, ("right",))
        self.assertEqual(rows[1].action_name, "context_use")


if __name__ == "__main__":
    unittest.main()
