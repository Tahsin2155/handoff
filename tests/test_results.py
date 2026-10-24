"""Tests for structured results and turn handling.

Run from the repo root with:  python -m unittest discover -s tests -t . -v
"""
from tests.stubs import (  # noqa: F401  (must be imported first: installs the fakes)
    Base, actions, blocked, call, click, fake_dialogs, require_confirmation, return_control,
)

import main  # noqa: E402
from executions import hands  # noqa: E402
from executions.results import OK, Outcome, Result  # noqa: E402

import unittest  # noqa: E402
from types import SimpleNamespace  # noqa: E402


class ResultTypeTests(Base):
    def test_only_ok_lets_the_turn_continue(self):
        for outcome in Outcome:
            self.assertEqual(Result(outcome).stops_turn, outcome is not Outcome.OK, outcome)

    def test_result_is_immutable(self):
        with self.assertRaises(Exception):
            OK.message = "changed"


class GatedActionTests(Base):
    def test_normal_action_runs_and_returns_ok(self):
        result = hands.click(x=500, y=500, intent="t")
        self.assertIs(result, OK)
        self.assertEqual([a[0] for a in actions], ["click"])

    def test_blocked_decision_does_not_run(self):
        result = hands.click(x=500, y=500, intent="t", safety_decision=blocked())
        self.assertEqual(result.outcome, Outcome.BLOCKED)
        self.assertEqual(result.message, "Blocked: Not allowed")
        self.assertEqual(actions, [])
        self.assertIn("warning", [kind for kind, _ in fake_dialogs.shown])

    def test_confirmation_denied_does_not_run(self):
        fake_dialogs.confirm_answer = False
        result = hands.click(x=500, y=500, intent="t", safety_decision=require_confirmation())
        self.assertEqual(result, Result(Outcome.DENIED, "Denied by user."))
        self.assertEqual(actions, [])

    def test_confirmation_approved_runs_once(self):
        fake_dialogs.confirm_answer = True
        result = hands.click(x=500, y=500, intent="t", safety_decision=require_confirmation())
        self.assertIs(result, OK)
        self.assertEqual([a[0] for a in actions], ["click"])


class RunTurnTests(Base):
    def test_all_steps_run_when_nothing_stops_them(self):
        steps = [click(), call("type", text="hi", intent="t")]
        feedback, stopped_by = main.run_turn(steps)
        self.assertEqual(feedback, [])
        self.assertIsNone(stopped_by)
        self.assertEqual([a[0] for a in actions], ["click", "typewrite"])

    def test_denied_step_stops_the_rest_of_the_batch(self):
        """A denied step must not let later steps run."""
        fake_dialogs.confirm_answer = False
        steps = [
            click(),                                        # runs
            SimpleNamespace(type="model_output", content="thinking"),  # not a call: ignored
            click(safety_decision=require_confirmation()),  # user says No
            call("type", text="rm -rf", intent="t", press_enter=True),  # must NOT run
            call("press_key", key="enter", intent="t"),                 # must NOT run
        ]
        feedback, stopped_by = main.run_turn(steps)
        self.assertEqual(stopped_by.outcome, Outcome.DENIED)
        self.assertEqual([a[0] for a in actions], ["click"])  # only the first click
        self.assertIn("click: Denied by user.", feedback)
        self.assertIn("Not executed because the turn stopped early: type, press_key", feedback)

    def test_blocked_step_stops_the_turn(self):
        steps = [click(safety_decision=blocked()), click()]
        feedback, stopped_by = main.run_turn(steps)
        self.assertEqual(stopped_by.outcome, Outcome.BLOCKED)
        self.assertEqual(actions, [])
        self.assertIn("click: Blocked: Not allowed", feedback)
        self.assertIn("Not executed because the turn stopped early: click", feedback)

    def test_unknown_function_stops_the_turn_and_is_reported(self):
        steps = [call("teleport"), click()]
        feedback, stopped_by = main.run_turn(steps)
        self.assertEqual(stopped_by.outcome, Outcome.UNKNOWN_FUNCTION)
        self.assertEqual(actions, [])
        self.assertTrue(any("teleport" in line for line in feedback))

    def test_return_control_stops_the_turn_and_passes_the_user_reply(self):
        fake_dialogs.input_answer = "go on"
        steps = [click(), return_control(), click()]
        feedback, stopped_by = main.run_turn(steps)
        self.assertEqual(stopped_by.outcome, Outcome.RETURN_CONTROL)
        self.assertEqual([a[0] for a in actions], ["click"])  # only the one before it
        self.assertEqual(feedback, [
            "return_control: The user replied: go on",
            "Not executed because the turn stopped early: click",
        ])

    def test_return_control_last_has_nothing_to_skip(self):
        fake_dialogs.input_answer = "thanks"
        feedback, stopped_by = main.run_turn([click(), return_control()])
        self.assertEqual(stopped_by.outcome, Outcome.RETURN_CONTROL)
        self.assertEqual(feedback, ["return_control: The user replied: thanks"])

    def test_blank_reply_ends_the_run(self):
        fake_dialogs.input_answer = None
        feedback, stopped_by = main.run_turn([return_control(), click()])
        self.assertEqual(stopped_by.outcome, Outcome.END_RUN)
        self.assertEqual(actions, [])
        self.assertEqual(feedback, ["Not executed because the turn stopped early: click"])


if __name__ == "__main__":
    unittest.main()
