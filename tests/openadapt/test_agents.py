"""Module for testing agents.

Note: requires valid OpenAI API key to run tests. May use disk space for caching.
"""

from io import StringIO
import sys

from PIL import Image
from transformers import Tool
import pytest

from openadapt import config
from openadapt.crud import get_latest_recording
from openadapt.strategies.mixins.agents import TransformersAgentsMixin

skip_no_recording = get_latest_recording() is None
skip_no_api_key = config.OPENAI_API_KEY == config._DEFAULTS["OPENAI_API_KEY"]


@pytest.mark.skipif(skip_no_recording, reason="no recording")
@pytest.mark.skipif(skip_no_api_key, reason="no api key")
def test_prompt() -> None:
    """Test prompting on a recording."""
    agent = TransformersAgentsMixin(
        recording=get_latest_recording(), api_key=config.OPENAI_API_KEY
    )
    assert agent.prompt(debug=False)


@pytest.mark.skipif(skip_no_api_key, reason="no api key")
def test_captioning() -> None:
    """Test captioning an image."""
    agent = TransformersAgentsMixin(recording=None, api_key=config.OPENAI_API_KEY)
    assert agent.chat("caption the image", image=Image.open("assets/visualize.png"))


# see https://huggingface.co/docs/transformers/custom_tools#using-custom-tools
# for more info
@pytest.mark.skipif(skip_no_api_key, reason="no api key")
def test_tools() -> None:
    """Test using a custom tool."""

    class StringReverser(Tool):
        """A tool that reverses a string."""

        name = "string_reverser"
        description = "reverses a string"
        inputs = ["text"]
        outputs = ["text"]

        def __call__(self, task: str) -> str:
            return task[::-1]

    tool = StringReverser()
    agent = TransformersAgentsMixin(
        recording=None,
        api_key=config.OPENAI_API_KEY,
        additional_tools=[tool],
    )
    f = StringIO()
    old = sys.stdout
    sys.stdout = f
    agent.run("reverse this string: hello openadapt")
    sys.stdout = old
    assert "hello openadapt"[::-1] in f.getvalue()


if __name__ == "__main__":
    agent = TransformersAgentsMixin(
        recording=get_latest_recording(), api_key=config.OPENAI_API_KEY
    )
    agent.prompt(debug=True)
