from __future__ import absolute_import, unicode_literals, print_function, division

import sublime_plugin
try:
    import queue
except ImportError:
    import Queue as queue

RESULTS = None
HACK_BUILD_SYSTEM = "Packages/SublimeREPL-ssh/sublimerepl_build_system_hack.sublime-build"
AUTOMATIC_BUILD_SYSTEM = ""


class SublimereplBuildSystemHackCommand(sublime_plugin.WindowCommand):
    def run(self, cmd):
        RESULTS.put(cmd)


def get_project_settings(window):
    global RESULTS
    try:
        RESULTS = queue.Queue()  # in case of garbage on RESULTS
        window.run_command("set_build_system", {"file": HACK_BUILD_SYSTEM})
        window.run_command("build")
    finally:
        window.run_command("set_build_system", {"file": AUTOMATIC_BUILD_SYSTEM})
    return RESULTS.get(timeout=1.0)
