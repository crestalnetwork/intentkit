"""Each tool must log under its own module name.

``record.name`` is the only per-tool identifier the JSON formatter emits
(``intentkit/utils/logging.py``), so a logger shared via a base-class attribute
would make every tool's records indistinguishable.
"""

import logging

from intentkit.core.system_tools import call_agent, create_post, current_time
from intentkit.core.system_tools.base import SystemTool
from intentkit.tools.base import IntentKitTool
from intentkit.tools.http.get import HttpGet


def test_system_tools_log_under_their_own_module():
    for tool in (call_agent, create_post, current_time):
        assert tool.logger.name == type(tool).__module__
        assert tool.logger.name != SystemTool.__module__


def test_system_tool_loggers_are_distinct():
    names = {t.logger.name for t in (call_agent, create_post, current_time)}
    assert len(names) == 3


def test_skill_tools_log_under_their_own_module():
    tool = HttpGet.model_construct()
    assert tool.logger.name == HttpGet.__module__
    assert tool.logger.name != IntentKitTool.__module__


def test_logger_is_a_real_logger():
    assert isinstance(current_time.logger, logging.Logger)
    # logging.getLogger caches, so repeated access is the same object.
    assert current_time.logger is current_time.logger
