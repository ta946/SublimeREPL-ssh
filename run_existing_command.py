from __future__ import absolute_import, unicode_literals, print_function, division

import os
import sys
import json
import sublime
import sublime_plugin

from .ansi.ansi_color_utils import ANSI_COLOR_DIR

SUBLIMEREPL_DIR = None
SUBLIMEREPL_USER_DIR = None

def _cleanup_ansi():
    repl_ids = []
    for window in sublime.windows():
        views = window.views()
        for view in views:
            repl_id = view.settings().get('repl_id')
            if not repl_id:
                continue
            repl_ids.append(repl_id)
    color_dir = os.path.join(sublime.packages_path(), ANSI_COLOR_DIR).replace('\\', '/')
    files = [f for f in os.listdir(color_dir)]
    for file_name in files:
        filetitle = os.path.splitext(file_name)[0]
        if filetitle not in repl_ids:
            file_path = os.path.join(color_dir, file_name)
            try:
                os.remove(file_path)
            except Exception as e:
                print(e)


def plugin_loaded():
    global SUBLIMEREPL_DIR
    global SUBLIMEREPL_USER_DIR
    SUBLIMEREPL_DIR = "Packages/SublimeREPL-ssh"
    SUBLIMEREPL_USER_DIR = os.path.join(sublime.packages_path(), "User", "SublimeREPL-ssh")
    if not os.path.exists(SUBLIMEREPL_USER_DIR):
        os.makedirs(SUBLIMEREPL_USER_DIR, exist_ok=True)
    _cleanup_ansi()

PY2 = False
if sys.version_info[0] == 2:
    SUBLIMEREPL_DIR = os.getcwdu()
    SUBLIMEREPL_USER_DIR = os.path.join(sublime.packages_path(), "User", "SublimeREPL-ssh")
    PY2 = True

# yes, CommandCommmand :) 
class RunExistingWindowCommandCommand(sublime_plugin.WindowCommand):
    def run(self, id, file):
        """Find and run existing command with id in specified file. 
        SUBLIMEREPL_USER_DIR is consulted first, and then SUBLIMEREPL_DIR""" 
        for prefix in (SUBLIMEREPL_USER_DIR, SUBLIMEREPL_DIR):
            path = os.path.join(prefix, file)
            json_cmd = self._find_cmd(id, path)
            if json_cmd:
                break
        if not json_cmd:
            return
        args = json_cmd["args"] if "args" in json_cmd else None
        self.window.run_command(json_cmd["command"], args)
    
    def _find_cmd(self, id, file):
        return self._find_cmd_in_file(id, file)
                
    def _find_cmd_in_file(self, id, file):
        try:
            if PY2 or os.path.isfile(file):
                with open(file) as f:
                    bytes = f.read()
            else:
                bytes = sublime.load_resource(file)
        except (IOError, ValueError):
            return None
        else:
            data = json.loads(bytes)
            return self._find_cmd_in_json(id, data)

    def _find_cmd_in_json(self, id, json_object):
        if isinstance(json_object, list):
            for elem in json_object:
                cmd = self._find_cmd_in_json(id, elem)
                if cmd:
                    return cmd
        elif isinstance(json_object, dict):
            if "id" in json_object and json_object["id"] == id:
                return json_object
            elif "children" in json_object:
                return self._find_cmd_in_json(id, json_object["children"])
        return None