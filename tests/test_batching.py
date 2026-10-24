"""Tests for batched function calls: pacing and the per-turn action limit."""
from tests.stubs import (  # noqa: F401  (installs the fakes)
    Base, actions, call, click, fake_dialogs, require_confirmation,
)

import unittest  # noqa: E402

import main  # noqa: E402
from executions.prompts import sys_instructions  # noqa: E402
from executions.tools import ACTION_GAP_SECONDS, MAX_ACTIONS_PER_TURN  # noqa: E402


class PacingTests(Base):
    def test_batch_runs_in_order_with_a_gap_between_actions(self):
        steps = [click(), call("type", text="hi", intent="t"), call("press_key", key="enter", intent="t")]
        main.run_turn(steps)
        self.assertEqual([a[0] for a in actions], ["click", "typewrite", "press"])
        self.assertEqual(self.sleeps, [ACTION_GAP_SECONDS, ACTION_GAP_SECONDS])  # 2 gaps for 3 actions

    def test_single_action_has_no_gap(self):
        main.run_turn([click()])
        self.assertEqual(self.sleeps, [])

    def test_no_gap_is_spent_after_the_turn_stops(self):
        fake_dialogs.confirm_answer = False
        steps = [click(), click(safety_decision=require_confirmation()), call("press_key", key="enter", intent="t")]
        main.run_turn(steps)
        self.assertEqual(self.sleeps, [ACTION_GAP_SECONDS])  # only before the 2nd action


class LimitTests(Base):
    def test_actions_beyond_the_limit_are_not_executed_and_reported(self):
        steps = [click() for _ in range(MAX_ACTIONS_PER_TURN + 2)]
        feedback, stopped_by = main.run_turn(steps)
        self.assertIsNone(stopped_by)  # the run continues; the model is just told
        self.assertEqual(len(actions), MAX_ACTIONS_PER_TURN)
        self.assertEqual(feedback, [
            f"Not executed because only {MAX_ACTIONS_PER_TURN} actions run per turn: click, click"
        ])

    def test_exactly_the_limit_is_fine(self):
        feedback, stopped_by = main.run_turn([click() for _ in range(MAX_ACTIONS_PER_TURN)])
        self.assertEqual((feedback, stopped_by), ([], None))
        self.assertEqual(len(actions), MAX_ACTIONS_PER_TURN)

    def test_limit_can_be_overridden(self):
        feedback, _ = main.run_turn([click(), click(), click()], max_actions=1)
        self.assertEqual(len(actions), 1)
        self.assertIn("only 1 actions run per turn: click, click", feedback[0])


class PromptTests(Base):
    def test_system_prompt_teaches_batching_with_the_real_limit(self):
        self.assertIn("## Batching actions", sys_instructions)
        self.assertIn(f"At most {MAX_ACTIONS_PER_TURN} actions per turn", sys_instructions)
        self.assertIn("Not executed because the turn stopped early", sys_instructions)


if __name__ == "__main__":
    unittest.main()
