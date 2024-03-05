# -*- coding: utf-8 -*-
# Copyright (c) 2011, Wojciech Bederski (wuub.net)
# All rights reserved.
# See LICENSE.txt for details.
from __future__ import absolute_import, unicode_literals, print_function, division

import os
import os.path
import threading
from datetime import datetime

import sublime
import sublime_plugin

try:
    import queue
    from .ansi import ansi_control, ansi_color_utils
    from .ansi.ansi_regex import ANSI_ESCAPE_8BIT_REGEX, ANSI_COLOR_REGEX
    from .repllibs import PyDbLite
except ImportError:
    import Queue as queue
    from ansi import ansi_control, ansi_color_utils
    from ansi.ansi_regex import ANSI_ESCAPE_8BIT_REGEX, ANSI_COLOR_REGEX
    from repllibs import PyDbLite
from . import SETTINGS_FILE

# import importlib; importlib.reload(repls.subprocess_repl);
# import importlib; importlib.reload(ansi_control);

SUBLIME2 = sublime.version() < '3000'
# READ_BUFFER = 1024
# READ_BUFFER = 2048
# READ_BUFFER = 8192
READ_BUFFER = 32_768
TERMINAL_HEIGHT = 24 # default


class ReplInsertTextCommand(sublime_plugin.TextCommand):
    def run(self, edit, pos, text):
        self.view.set_read_only(False)  # make sure view is writable
        self.view.insert(edit, int(pos), text)


class ReplEraseTextCommand(sublime_plugin.TextCommand):
    def run(self, edit, start, end):
        self.view.set_read_only(False)  # make sure view is writable
        self.view.erase(edit, sublime.Region(int(start), int(end)))


class ReplPass(sublime_plugin.TextCommand):
    def run(self, edit):
        pass


class ReplReader(threading.Thread):
    def __init__(self, repl):
        super(ReplReader, self).__init__()
        self.repl = repl
        self.daemon = True
        self.queue = queue.Queue()

    def run(self):
        r = self.repl
        q = self.queue
        while True:
            result = r.read()
            q.put(result)
            if result is None:
                break


class HistoryMatchList(object):
    def __init__(self, command_prefix, commands):
        self._command_prefix = command_prefix
        self._commands = commands
        self._cur = len(commands)  # no '-1' on purpose

    def current_command(self):
        if not self._commands:
            return ""
        return self._commands[self._cur]

    def prev_command(self):
        self._cur = max(0, self._cur - 1)
        return self.current_command()

    def next_command(self):
        self._cur = min(len(self._commands) - 1, self._cur + 1)
        return self.current_command()


class History(object):
    def __init__(self):
        self._last = None

    def push(self, command):
        cmd = command.rstrip()
        if not cmd or cmd == self._last:
            return
        self.append(cmd)
        self._last = cmd

    def append(self, cmd):
        raise NotImplementedError()

    def match(self, command_prefix):
        raise NotImplementedError()


class MemHistory(History):
    def __init__(self):
        super(MemHistory, self).__init__()
        self._stack = []

    def append(self, cmd):
        self._stack.append(cmd)

    def match(self, command_prefix):
        matching_commands = []
        for cmd in self._stack:
            if cmd.startswith(command_prefix):
                matching_commands.append(cmd)
        return HistoryMatchList(command_prefix, matching_commands)


class PersistentHistory(MemHistory):
    def __init__(self, external_id):
        super(PersistentHistory, self).__init__()
        path = os.path.join(sublime.packages_path(), "User", ".SublimeREPLHistory")
        if not os.path.isdir(path):
            os.makedirs(path)
        filepath = os.path.join(path, external_id + ".db")
        self._db = PyDbLite.Base(filepath)
        self._external_id = external_id
        self._db.create("external_id", "command", "ts", mode="open")

    def append(self, cmd):
        self._db.insert(external_id=self._external_id, command=cmd, ts=datetime.now())
        self._db.commit()

    def match(self, command_prefix):
        retults = [cmd for cmd in self._db if cmd["command"].startswith(command_prefix)]
        return HistoryMatchList(command_prefix, [x["command"] for x in retults])


class ReplView(object):
    def __init__(self, view, repl, syntax, repl_restart_args):
        self._ansi_controller = None
        self.repl = repl
        self.repl._rv = self
        self._view = view
        self._window = view.window()
        self._repl_launch_args = repl_restart_args
        # list of callable(repl) to handle view close events
        self.call_on_close = []
        self._read_buffer = READ_BUFFER

        if syntax:
            view.set_syntax_file(syntax)
        self._output_end = view.size()
        self._prompt_size = 0

        self._repl_reader = ReplReader(repl)
        self._repl_reader.start()

        settings = sublime.load_settings(SETTINGS_FILE)

        view.settings().set("repl_external_id", repl.external_id)
        view.settings().set("repl_id", repl.id)
        view.settings().set("repl", True)
        view.settings().set("repl_sublime2", SUBLIME2)
        if repl.allow_restarts():
            view.settings().set("repl_restart_args", repl_restart_args)

        rv_settings = settings.get("repl_view_settings", {})
        for setting, value in list(rv_settings.items()):
            view.settings().set(setting, value)

        view.settings().set("history_arrows", settings.get("history_arrows", True))

        # for hysterical rasins ;)
        persistent_history_enabled = settings.get("persistent_history_enabled") or settings.get("presistent_history_enabled")
        if self.external_id and persistent_history_enabled:
            self._history = PersistentHistory(self.external_id)
        else:
            self._history = MemHistory()
        self._history_match = None

        self._filter_color_codes = settings.get("filter_ascii_color_codes")
        self._emulate_ansi_csi = settings.get("emulate_ansi_csi")
        self._ansi_limit_cursor_up = settings.get("ansi_limit_cursor_up")
        self._debug_ansi = settings.get("debug_ansi", False)
        if self._emulate_ansi_csi:
            self._ansi_controller = ansi_control.AnsiControl(self, is_ansi_allow_color=not self._filter_color_codes,
                                                             terminal_height=TERMINAL_HEIGHT,
                                                             limit_cursor_up=self._ansi_limit_cursor_up)
            if not self._filter_color_codes:
                ansi_color_utils.init_ansi_color(self)
        self._ansi_escape_8bit_regex = ANSI_ESCAPE_8BIT_REGEX

        # optionally move view to a different group
        # find current position of this replview
        (group, index) = self._window.get_view_index(view)

        # get the view that was focussed before the repl was opened.
        # we'll have to focus this one briefly to make sure it's in the
        # foreground again after moving the replview away
        oldview = self._window.views_in_group(group)[max(0, index - 1)]

        target = settings.get("open_repl_in_group")

        # either the target group is specified by index
        if isinstance(target, int):
            if 0 <= target < self._window.num_groups() and target != group:
                self._window.set_view_index(view, target, len(self._window.views_in_group(target)))
                self._window.focus_view(oldview)
                self._window.focus_view(view)
        ## or, if simply set to true, move it to the next group from the currently active one
        elif target and group + 1 < self._window.num_groups():
            self._window.set_view_index(view, group + 1, len(self._window.views_in_group(group + 1)))
            self._window.focus_view(oldview)
            self._window.focus_view(view)

        # begin refreshing attached view
        self.update_view_loop()

    @property
    def external_id(self):
        return self.repl.external_id

    def on_backspace(self):
        if self.delta < 0:
            self._view.run_command("left_delete")

    def on_ctrl_backspace(self):
        if self.delta < 0:
            self._view.run_command("delete_word", {"forward": False, "sub_words": True})

    def on_super_backspace(self):
        if self.delta < 0:
            for i in range(abs(self.delta)):
                self._view.run_command("left_delete")  # Hack to delete to BOL

    def on_left(self):
        if self.delta != 0:
            self._window.run_command("move", {"by": "characters", "forward": False, "extend": False})

    def on_shift_left(self):
        if self.delta != 0:
            self._window.run_command("move", {"by": "characters", "forward": False, "extend": True})

    def on_home(self):
        if self.delta > 0:
            self._window.run_command("move_to", {"to": "bol", "extend": False})
        else:
            for i in range(abs(self.delta)):
                self._window.run_command("move", {"by": "characters", "forward": False, "extend": False})

    def on_shift_home(self):
        if self.delta > 0:
            self._window.run_command("move_to", {"to": "bol", "extend": True})
        else:
            for i in range(abs(self.delta)):
                self._window.run_command("move", {"by": "characters", "forward": False, "extend": True})

    def on_tab(self):
        if self.repl.TYPE != "ssh_paramiko":
            return
        self.repl._interceptor_handler._process_tab(self.user_input)

    def on_selection_modified(self):
        self._view.set_read_only(self.delta > 0)

    def on_close(self):
        self.repl.close()
        for fun in self.call_on_close:
            fun(self)

    def clear(self, edit):
        self.escape(edit)
        self._view.erase(edit, self.output_region)
        self._output_end = self._view.sel()[0].begin()

    def escape(self, edit):
        self._view.set_read_only(False)
        self._view.erase(edit, self.input_region)
        self._view.show(self.input_region)

    def enter(self):
        v = self._view
        if v.sel()[0].begin() != v.size():
            v.sel().clear()
            v.sel().add(sublime.Region(v.size()))

        l = self._output_end

        self.push_history(self.user_input)  # don't include cmd_postfix in history
        v.run_command("insert", {"characters": self.repl.cmd_postfix})
        command = self.user_input
        self.adjust_end()

        if self.repl.apiv2:
            self.repl.write(command, location=l)
        else:
            self.repl.write(command)

    def previous_command(self, edit):
        self._view.set_read_only(False)
        self.ensure_history_match()
        self.replace_current_input(edit, self._history_match.prev_command())
        self._view.show(self.input_region)

    def next_command(self, edit):
        self._view.set_read_only(False)
        self.ensure_history_match()
        self.replace_current_input(edit, self._history_match.next_command())
        self._view.show(self.input_region)

    def update_view(self, view):
        """If projects were switched, a view could be a new instance"""
        if self._view is not view:
            self._view = view

    def adjust_end(self):
        if self.repl.suppress_echo:
            v = self._view
            vsize = v.size()
            self._output_end = min(vsize, self._output_end)
            v.run_command("repl_erase_text", {"start": self._output_end, "end": vsize})
        else:
            self._output_end = self._view.size()
        if self._emulate_ansi_csi:
            self._ansi_controller._cursor_pos = self._output_end

    def write(self, unistr):
        """Writes output from Repl into this view."""
        if self._emulate_ansi_csi:
            try:
                self._ansi_controller.run(unistr, debug=self._debug_ansi)
            except Exception as e:
                print(e)
                print(unistr)
                sublime.error_message("Error in ansi controller!")
        else:
            # remove color codes
            if self._filter_color_codes:
                unistr = self._ansi_escape_8bit_regex.sub('', unistr)
                unistr = ANSI_COLOR_REGEX.sub('', unistr)

            # string is assumed to be already correctly encoded
            self._view.run_command("repl_insert_text", {"pos": self._output_end - self._prompt_size, "text": unistr})
            self._output_end += len(unistr)
        self._view.show(self.input_region)

    def write_prompt(self, unistr):
        """Writes prompt from REPL into this view. Prompt is treated like
           regular output, except output is inserted before the prompt."""
        self._prompt_size = 0
        self.write(unistr)
        self._prompt_size = len(unistr)

    def append_input_text(self, text, edit=None):
        if edit:
            self._view.insert(edit, self._view.size(), text)
        else:
            self._view.run_command("repl_insert_text", {"pos": self._view.size(), "text": text})

    def get_view_text(self):
        text = self._view.substr(sublime.Region(0, self._view.size()))
        return text

    def clear_queue(self):
        with self._repl_reader.queue.mutex:
            self._repl_reader.queue.queue.clear()

    def handle_repl_output(self):
        """Returns new data from Repl and bool indicating if Repl is still
           working"""
        ret = True
        text = ''
        try:
            while self.repl.is_alive():
                packet = self._repl_reader.queue.get_nowait()
                if packet is None:
                    ret = False
                    break
                text += packet
                if len(text) >= self._read_buffer:
                    self.handle_repl_packet(text)
                    text = ''
        except queue.Empty:
            pass
        if len(text):
            self.handle_repl_packet(text)
        return ret

    def handle_repl_packet(self, packet):
        if self.repl.apiv2:
            for opcode, data in packet:
                if opcode == 'output':
                    self.write(data)
                elif opcode == 'prompt':
                    self.write_prompt(data)
                elif opcode == 'highlight':
                    a, b = data
                    regions = self._view.get_regions('sublimerepl')
                    regions.append(sublime.Region(a, b))
                    self._view.add_regions('sublimerepl', regions, 'invalid',
                                           '', sublime.DRAW_EMPTY | sublime.DRAW_OUTLINED)
                else:
                    print('SublimeREPL: unknown REPL opcode: ' + opcode)
        else:
            self.write(packet)

    def _update_view_loop(self):
        from time import sleep
        is_still_working = True
        while is_still_working:
            is_still_working = self.handle_repl_output()
            sleep(0.01)

        self.write("\n***Repl Killed***\n""" if self.repl._killed else "\n***Repl Closed***\n""")
        self._view.set_read_only(True)
        if sublime.load_settings(SETTINGS_FILE).get("view_auto_close"):
            window = self._view.window()
            if window is not None:
                window.focus_view(self._view)
                window.run_command("close")

    def update_view_loop(self):
        self._t = threading.Thread(target=self._update_view_loop)
        self._t.start()

    def push_history(self, command):
        self._history.push(command)
        self._history_match = None

    def ensure_history_match(self):
        user_input = self.user_input
        if self._history_match is not None:
            if user_input != self._history_match.current_command():
                # user did something! reset
                self._history_match = None
        if self._history_match is None:
            self._history_match = self._history.match(user_input)

    def replace_current_input(self, edit, cmd):
        if cmd:
            self._view.replace(edit, self.input_region, cmd)
            self._view.sel().clear()
            self._view.sel().add(sublime.Region(self._view.size()))

    def run(self, edit, code):
        self.replace_current_input(edit, code)
        self.enter()
        self._view.show(self.input_region)
        self._window.focus_view(self._view)

    @property
    def view(self):
        return self._view

    @property
    def input_region(self):
        return sublime.Region(self._output_end, self._view.size())

    @property
    def output_region(self):
        return sublime.Region(0, self._output_end - 2)

    @property
    def user_input(self):
        """Returns text entered by the user"""
        return self._view.substr(self.input_region)

    @property
    def delta(self):
        """Return a repl_view and number of characters from current selection
        to then begging of user_input (otherwise known as _output_end)"""
        return self._output_end - self._view.sel()[0].begin()

    def allow_deletion(self):
        # returns true if all selections falls in user input
        # and can be safetly deleted
        output_end = self._output_end
        for sel in self._view.sel():
            if sel.begin() == sel.end() and sel.begin() == output_end:
                # special case, when single selecion
                # is at the very beggining of prompt
                return False
            # i don' really know if end() is always after begin()
            if sel.begin() < output_end or sel.end() < output_end:
                return False
        return True
