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
        vi_intrcpt_hndlr = rv.repl._interceptor_handler
        src_path = self.view.settings().get('SublimeREPL-ssh-sftp.src_path')
        dest_path = self.view.settings().get('SublimeREPL-ssh-sftp.dest_path')
        if not src_path or not dest_path:
            return
        self.view.set_status('SublimeREPL-ssh', f'uploading {dest_path}...')
        vi_intrcpt_hndlr.put_file(src_path, dest_path)
        self.view.set_status('SublimeREPL-ssh', f'uploaded {dest_path}')

    def on_close(self):
        rv = manager.repl_views.get(self.view.settings().get('view_repl_id'), None)
        if not rv:
            return
        self.view.erase_status('SublimeREPL-ssh')
        path = self.view.file_name()
        if os.path.exists(path):
            os.remove(path)
