import sublime
import sublime_plugin

from .repl_manager import ReplManager


manager = ReplManager()


# Window Commands #########################################


# Opens a new REPL
class ReplOpenCommand(sublime_plugin.WindowCommand):
    def run(self, encoding, type, syntax=None, view_id=None, **kwds):
        manager.open(self.window, encoding, type, syntax, view_id, **kwds)


class ReplRestartCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        manager.restart(self.view, edit)

    def is_visible(self):
        if not self.view:
            return False
        return bool(self.view.settings().get("repl_restart_args", None))

    def is_enabled(self):
        return self.is_visible()

# REPL Comands ############################################


# Submits the Command to the REPL
class ReplEnterCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        rv = manager.repl_view(self.view)
        if rv:
            rv.enter()


class ReplClearCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        rv = manager.repl_view(self.view)
        if rv:
            rv.clear(edit)


# Resets Repl Command Line
class ReplEscapeCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        rv = manager.repl_view(self.view)
        if rv:
            rv.escape(edit)


def repl_view_delta(sublime_view):
    """Return a repl_view and number of characters from current selection
    to then beggingin of user_input (otherwise known as _output_end)"""
    rv = manager.repl_view(sublime_view)
    if not rv:
        return None, -1
    delta = rv._output_end - sublime_view.sel()[0].begin()
    return rv, delta


class ReplBackspaceCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        rv = manager.repl_view(self.view)
        if rv:
            rv.on_backspace()


class ReplCtrlBackspaceCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        rv = manager.repl_view(self.view)
        if rv:
            rv.on_ctrl_backspace()


class ReplSuperBackspaceCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        rv = manager.repl_view(self.view)
        if rv:
            rv.on_super_backspace()


class ReplLeftCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        rv = manager.repl_view(self.view)
        if rv:
            rv.on_left()


class ReplShiftLeftCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        rv = manager.repl_view(self.view)
        if rv:
            rv.on_shift_left()


class ReplHomeCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        rv = manager.repl_view(self.view)
        if rv:
            rv.on_home()


class ReplShiftHomeCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        rv = manager.repl_view(self.view)
        if rv:
            rv.on_shift_home()


class ReplViewPreviousCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        rv = manager.repl_view(self.view)
        if rv:
            rv.previous_command(edit)


class ReplViewNextCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        rv = manager.repl_view(self.view)
        if rv:
            rv.next_command(edit)


class ReplTabCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        rv = manager.repl_view(self.view)
        if rv:
            rv.on_tab()


class ReplKillCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        rv = manager.repl_view(self.view)
        if rv:
            rv.repl.kill()

    def is_visible(self):
        rv = manager.repl_view(self.view)
        return bool(rv)

    def is_enabled(self):
        return self.is_visible()


class SublimeReplListener(sublime_plugin.EventListener):
    def on_selection_modified(self, view):
        rv = manager.repl_view(view)
        if rv:
            rv.on_selection_modified()

    def on_close(self, view):
        rv = manager.repl_view(view)
        if rv:
            rv.on_close()

    def on_text_command(self, view, command_name, args):
        rv = manager.repl_view(view)
        if not rv:
            return None

        if command_name == 'left_delete':
            # stop backspace on ST3 w/o breaking brackets
            if not rv.allow_deletion():
                return 'repl_pass', {}

        if command_name == 'delete_word' and not args.get('forward'):
            # stop ctrl+backspace on ST3 w/o breaking brackets
            if not rv.allow_deletion():
                return 'repl_pass', {}

        return None

class SubprocessReplSendSignal(sublime_plugin.TextCommand):
    def run(self, edit, signal=None):
        rv = manager.repl_view(self.view)
        subrepl = rv.repl
        signals = subrepl.available_signals()
        sorted_names = sorted(signals.keys())
        if signal in signals:
            #signal given by name
            self.safe_send_signal(subrepl, signals[signal])
            return
        if signal in list(signals.values()):
            #signal given by code (correct one!)
            self.safe_send_signal(subrepl, signal)
            return

        # no or incorrect signal given
        def signal_selected(num):
            if num == -1:
                return
            signame = sorted_names[num]
            sigcode = signals[signame]
            self.safe_send_signal(subrepl, sigcode)
        self.view.window().show_quick_panel(sorted_names, signal_selected)

    def safe_send_signal(self, subrepl, sigcode):
        try:
            subrepl.send_signal(sigcode)
        except Exception as e:
            sublime.error_message(str(e))

    def is_visible(self):
        rv = manager.repl_view(self.view)
        return bool(rv) and hasattr(rv.repl, "send_signal")

    def is_enabled(self):
        return self.is_visible()

    def description(self):
        return "Send SIGNAL"
