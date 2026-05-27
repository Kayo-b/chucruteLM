from __future__ import annotations

import unittest

from chucrutelm.control import ActionExecutor, button_name_to_linux_code, key_name_to_linux_code
from chucrutelm.profiles import GameProfile, build_tibia_profile


class _FakeBackend:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []
        self.closed = False

    def press_key(self, key_name: str) -> None:
        self.events.append(("press_key", key_name))

    def release_key(self, key_name: str) -> None:
        self.events.append(("release_key", key_name))

    def press_button(self, button_name: str) -> None:
        self.events.append(("press_button", button_name))

    def release_button(self, button_name: str) -> None:
        self.events.append(("release_button", button_name))

    def close(self) -> None:
        self.closed = True


class _FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, duration: float) -> None:
        self.sleeps.append(duration)
        self.now += duration


class ActionRuntimeTest(unittest.TestCase):
    def test_linux_code_mapping_supports_common_inputs(self) -> None:
        self.assertGreater(key_name_to_linux_code("up"), 0)
        self.assertGreater(key_name_to_linux_code("space"), 0)
        self.assertGreater(key_name_to_linux_code("a"), 0)
        self.assertGreater(button_name_to_linux_code("left"), 0)

    def test_action_executor_supports_hold_tap_and_click_actions(self) -> None:
        profile = GameProfile.generic(
            name="test-profile",
            action_names=["noop", "move_up", "next_target", "attack"],
            key_bindings={"move_up": ("up",), "next_target": ("space",)},
            button_bindings={"attack": ("left",)},
            held_key_actions=("move_up",),
            tapped_key_actions=("next_target",),
            clicked_button_actions=("attack",),
        )
        backend = _FakeBackend()
        clock = _FakeClock()
        executor = ActionExecutor(
            profile=profile,
            backend=backend,
            key_press_s=0.05,
            key_repeat_s=0.2,
            button_press_s=0.05,
            button_repeat_s=0.2,
            time_fn=clock.time,
            sleep_fn=clock.sleep,
        )

        result = executor.apply("move_up")
        self.assertEqual(result.held_keys, ("up",))
        self.assertEqual(result.tapped_keys, ())
        self.assertEqual(result.clicked_buttons, ())
        self.assertEqual(backend.events, [("press_key", "up")])

        backend.events.clear()
        result = executor.apply("move_up")
        self.assertEqual(result.held_keys, ("up",))
        self.assertEqual(result.tapped_keys, ())
        self.assertEqual(result.clicked_buttons, ())
        self.assertEqual(backend.events, [])

        backend.events.clear()
        result = executor.apply("next_target")
        self.assertEqual(result.held_keys, ())
        self.assertEqual(result.tapped_keys, ("space",))
        self.assertEqual(result.clicked_buttons, ())
        self.assertEqual(
            backend.events,
            [
                ("release_key", "up"),
                ("press_key", "space"),
                ("release_key", "space"),
            ],
        )
        self.assertEqual(clock.sleeps, [0.05])

        backend.events.clear()
        result = executor.apply("next_target")
        self.assertEqual(result.tapped_keys, ())
        self.assertEqual(backend.events, [])

        clock.now += 0.25
        backend.events.clear()
        result = executor.apply("attack")
        self.assertEqual(result.held_keys, ())
        self.assertEqual(result.tapped_keys, ())
        self.assertEqual(result.clicked_buttons, ("left",))
        self.assertEqual(
            backend.events,
            [
                ("press_button", "left"),
                ("release_button", "left"),
            ],
        )
        self.assertEqual(clock.sleeps, [0.05, 0.05])

        backend.events.clear()
        result = executor.apply("attack")
        self.assertEqual(result.clicked_buttons, ())
        self.assertEqual(backend.events, [])

        clock.now += 0.25
        result = executor.apply("attack")
        self.assertEqual(result.clicked_buttons, ("left",))

        executor.close()
        self.assertTrue(backend.closed)

    def test_tibia_profile_uses_tibia_defaults(self) -> None:
        profile = build_tibia_profile(action_names=["move_up", "move_up_left", "attack_interact", "open_battle_list"])
        self.assertEqual(profile.tapped_keys_for_action("move_up"), ("up",))
        self.assertEqual(profile.tapped_keys_for_action("move_up_left"), ("kp7",))
        self.assertEqual(profile.clicked_buttons_for_action("attack_interact"), ("left",))
        self.assertEqual(profile.tapped_keys_for_action("open_battle_list"), ("ctrl_l", "b"))
        self.assertEqual(
            profile.infer_action({"pressed_keys": ("ctrl_l", "b"), "pressed_buttons": ()}),
            "open_battle_list",
        )
        self.assertEqual(
            profile.infer_action({"pressed_keys": ("w",), "pressed_buttons": ()}),
            "move_up",
        )
        shortcut_profile = build_tibia_profile(action_names=["move_down", "open_skills_window"])
        self.assertEqual(
            shortcut_profile.infer_action({"pressed_keys": ("ctrl_l", "s"), "pressed_buttons": ()}),
            "open_skills_window",
        )


if __name__ == "__main__":
    unittest.main()
