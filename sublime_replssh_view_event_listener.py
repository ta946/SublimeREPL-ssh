import sublime
import sublime_plugin

import os

from .repl_manager_init import manager


class SublimeReplsshViewEventListener(sublime_plugin.ViewEventListener):
    @classmethod
    def is_applicable(cls, settings):
        return settings.get('SublimeREPL-ssh-sftp')

    def on_post_save_async(self):
        rv = manager.repl_views.get(self.view.settings().get('view_repl_id'), None)
        if not rv:
            return
        vi_intrcpt_hndlr = rv.repl._vi_interceptor_handler
        if vi_intrcpt_hndlr.dest_path is None or vi_intrcpt_hndlr.src_path is None:
            return
        self.view.set_status('SublimeREPL-ssh', f'uploading {vi_intrcpt_hndlr.dest_path}...')
        vi_intrcpt_hndlr.put_file(vi_intrcpt_hndlr.src_path, vi_intrcpt_hndlr.dest_path)
        self.view.set_status('SublimeREPL-ssh', f'uploaded {vi_intrcpt_hndlr.dest_path}')

    def on_close(self):
        rv = manager.repl_views.get(self.view.settings().get('view_repl_id'), None)
        if not rv:
            return
        vi_intrcpt_hndlr = rv.repl._vi_interceptor_handler
        self.view.erase_status('SublimeREPL-ssh')
        vi_intrcpt_hndlr.src_path = None
        vi_intrcpt_hndlr.dest_path = None
        path = self.view.file_name()
        if os.path.exists(path):
            os.remove(path)
