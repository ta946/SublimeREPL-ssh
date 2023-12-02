import sublime
import sublime_plugin

import sys
import os
import traceback

from . import SETTINGS_FILE, CAN_USE_PARAMIKO
from . import sublimerepl_build_system_hack
from .sublimerepl import ReplView
from .repls.repl import Repl


PLATFORM = sublime.platform().lower()
unicode_type = str
PY2 = False


RESTART_MSG = """
#############
## RESTART ##
#############
"""

class ReplManager(object):

    def __init__(self):
        self.repl_views = {}

    def repl_view(self, view):
        repl_id = view.settings().get("repl_id")
        if repl_id not in self.repl_views:
            return None
        rv = self.repl_views[repl_id]
        rv.update_view(view)
        return rv

    def find_repl(self, external_id):
        """Yields rvews matching external_id taken from source.[external_id] scope
           Match is done on external_id value of repl and additional_scopes"""
        for rv in self.repl_views.values():
            if not (rv.repl and rv.repl.is_alive()):
                continue  # dead repl, skip
            rvid = rv.external_id
            additional_scopes = rv.repl.additional_scopes
            if rvid == external_id or external_id in additional_scopes:
                yield rv

    @staticmethod
    def _check_paramiko(type, kwds):
        if type.upper() != 'SSH_PARAMIKO':
            return type, kwds
        if not sublime.load_settings(SETTINGS_FILE).get("use_paramiko", False) or not CAN_USE_PARAMIKO:
            type = 'ssh'
            user = kwds.pop('user')
            ip = kwds.pop('ip')
            key = kwds.pop('key')
            kwds['cmd'] = ["ssh", "-tt", "-i", key, f"{user}@{ip}"]
        return type, kwds

    def open(self, window, encoding, type, syntax=None, view_id=None, title=None, **kwds):
        type, kwds = self._check_paramiko(type, kwds)
        repl_restart_args = {
            'encoding': encoding,
            'type': type,
            'syntax': syntax,
        }
        repl_restart_args.update(kwds)
        try:
            kwds = ReplManager.translate(window, kwds)
            encoding = ReplManager.translate(window, encoding)
            r = Repl.subclass(type)(encoding, **kwds)
            found = None
            for view in window.views():
                if view.id() == view_id:
                    found = view
                    break
            view = found or window.new_file()

            rv = ReplView(view, r, syntax, repl_restart_args)
            rv.call_on_close.append(self._delete_repl)
            self.repl_views[r.id] = rv
            view.set_scratch(True)
            if title is None:
                title = "*REPL* [%s]" % (r.name(),)
            view.set_name(title)
            return rv
        except Exception as e:
            traceback.print_exc()
            sublime.error_message(repr(e))

    def restart(self, view, edit):
        repl_restart_args = view.settings().get("repl_restart_args")
        if not repl_restart_args:
            sublime.message_dialog("No restart parameters found")
            return False
        rv = self.repl_view(view)
        if rv:
            if rv.repl and rv.repl.is_alive() and not sublime.ok_cancel_dialog("Still running. Really restart?"):
                return False
            rv.on_close()  # yes on_close, delete rv from

        view.insert(edit, view.size(), RESTART_MSG)
        repl_restart_args["view_id"] = view.id()
        self.open(view.window(), **repl_restart_args)
        return True

    def _delete_repl(self, repl_view):
        repl_id = repl_view.repl.id
        if repl_id not in self.repl_views:
            return None
        del self.repl_views[repl_id]

    @staticmethod
    def translate(window, obj, subst=None):
        if subst is None:
            subst = ReplManager._subst_for_translate(window)
        if isinstance(obj, dict):
            return ReplManager._translate_dict(window, obj, subst)
        if isinstance(obj, unicode_type):  # PY2
            return ReplManager._translate_string(window, obj, subst)
        if isinstance(obj, list):
            return ReplManager._translate_list(window, obj, subst)
        return obj

    @staticmethod
    def _subst_for_translate(window):
        """ Return all available substitutions"""
        import locale
        res = {
            "packages": sublime.packages_path(),
            "installed_packages": sublime.installed_packages_path()
        }
        if window.folders():
            res["folder"] = window.folders()[0]
        res["editor"] = "subl -w"
        res["win_cmd_encoding"] = "utf8"
        if sublime.platform() == "windows":
            res["win_cmd_encoding"] = locale.getdefaultlocale()[1]
            res["editor"] = '"%s"' % (sys.executable,)
        av = window.active_view()
        if av is None:
            return res
        filename = av.file_name()
        if not filename:
            return res
        filename = os.path.abspath(filename)
        res["file"] = filename
        res["file_path"] = os.path.dirname(filename)
        res["file_basename"] = os.path.basename(filename)
        if 'folder' not in res:
            res["folder"] = res["file_path"]

        if sublime.load_settings(SETTINGS_FILE).get("use_build_system_hack", False):
            project_settings = sublimerepl_build_system_hack.get_project_settings(window)
            res.update(project_settings)

        return res

    @staticmethod
    def _translate_string(window, string, subst=None):
        from string import Template
        if subst is None:
            subst = ReplManager._subst_for_translate(window)

        # see #200, on older OSX (10.6.8) system wide python won't accept
        # dict(unicode -> unicode) as **argument.
        # It's best to just str() keys, since they are ascii anyway
        if PY2:
            subst = dict((str(key), val) for key, val in subst.items())

        return Template(string).safe_substitute(**subst)

    @staticmethod
    def _translate_list(window, list, subst=None):
        if subst is None:
            subst = ReplManager._subst_for_translate(window)
        return [ReplManager.translate(window, x, subst) for x in list]

    @staticmethod
    def _translate_dict(window, dictionary, subst=None):
        if subst is None:
            subst = ReplManager._subst_for_translate(window)
        if PLATFORM in dictionary:
            return ReplManager.translate(window, dictionary[PLATFORM], subst)
        for k, v in list(dictionary.items()):
            dictionary[k] = ReplManager.translate(window, v, subst)
        return dictionary
