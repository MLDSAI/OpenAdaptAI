"""
Tests whether the lmql mixin can return valid action events
"""
from loguru import logger
from lmql.runtime.bopenai import get_stats

from openadapt.strategies.mixins.lmql_action import LMQLReplayStrategyMixin
from openadapt.models import Recording, ActionEvent

RECORDING = Recording()


class LMQLReplayStrategy(LMQLReplayStrategyMixin):
    """Custom Replay Strategy to solely test the LMQL Mixin."""

    def __init__(self, recording: Recording):
        super().__init__(recording)

    def get_next_action_event(self):
        pass


REPLAY = LMQLReplayStrategy(RECORDING)

def test_press():
    prompt = "Penelope entered 'P' into the website."
    actual = REPLAY.get_valid_action_event(prompt)
    expected = ActionEvent(name="press", key_name= "P")
    logger.info(get_stats()) # log OpenAI API Stats
    assert actual == expected

def test_release():
    prompt = "Penelope stopped entering 'N' into the website."
    actual = REPLAY.get_valid_action_event(prompt)
    expected = ActionEvent(name="release", key_name= "N")
    logger.info(get_stats()) # log OpenAI API Stats
    assert actual == expected

def test_scroll():
    prompt = "Cynthia scrolled 4 pixels down."
    actual = REPLAY.get_valid_action_event(prompt)
    expected = ActionEvent(name="scroll", mouse_dx="0", mouse_dy="4")
    logger.info(get_stats()) # log OpenAI API Stats
    assert actual == expected

def test_click():
    prompt = "The user opened a file in the middle of the screen of a macbook with 1440 width and 900 height."
    actual = REPLAY.get_valid_action_event(prompt)
    expected = ActionEvent(name="click", mouse_x="720", mouse_y="450", mouse_button_name="left")
    logger.info(get_stats()) # log OpenAI API Stats
    assert actual == expected

def test_move():
    prompt = "Theodore displaced her mouse from the top right of the 1440 width and 900 height screen to the middle of the screen."
    actual = REPLAY.get_valid_action_event(prompt)
    expected = ActionEvent(name="move", mouse_x="720", mouse_y="450")
    logger.info(get_stats()) # log OpenAI API Stats
    assert actual == expected
