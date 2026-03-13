import logging

from app.logging_setup import set_debug_mode


def test_set_debug_mode_sets_levels():
    root = logging.getLogger()
    root.setLevel(logging.WARNING)

    set_debug_mode(False)
    assert root.level == logging.INFO

    set_debug_mode(True)
    assert root.level == logging.DEBUG
