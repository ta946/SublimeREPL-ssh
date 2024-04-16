import sublime

import os
from queue import Queue, Empty

from ..sublimerepl import SETTINGS_FILE

SFTP_DIRECTORY = os.path.join(sublime.packages_path(), 'SublimeREPL-ssh/repls/sftp').replace('\\', '/')


class Interceptor:
    def __init__(self, sftp_directory=SFTP_DIRECTORY, intercept_vi=None, is_cmd=False):
        self._sftp_directory = sftp_directory
        self._intercept_recv = False
        self._is_cmd = is_cmd

        settings = sublime.load_settings(SETTINGS_FILE)
        self._is_intercept_vi = bool(intercept_vi if intercept_vi is not None else settings.get("paramiko_intercept_vi"))

    def _read_bytes(self):
        while True:
            ret, _bytes = self._repl._recv()
            if not ret:
                return
            elif _bytes:
                if self._intercept_recv:
                    self._recv_Q.put(_bytes)
                    continue
                return _bytes

    def _write_bytes(self, _bytes):
        ret = self.process(_bytes)
        if ret:
            return
        self._repl._write_bytes(_bytes)

    def _recv_intercepted(self):
        _bytes = b''
        for _ in range(5):
            try:
                _bytes += self._recv_Q.get(timeout=0.01)
            except Empty:
                pass
        return _bytes

    def _post_process_intercept_cmd_win(self, _bytes):
        if not _bytes:
            return None
        if _bytes.endswith(b'\x08'):
            _bytes = _bytes[:-2]
        result = self._repl._ansi_escape_8bit.sub(b'', _bytes).strip()
        results = [result]
        return results

    def _post_process_intercept_cmd_unix(self, _bytes):
        _bytes_split = _bytes.split(b'\n')
        if len(_bytes_split) <= 2:
            return None
        results = _bytes_split[1:-1]
        results[0] = self._repl._ansi_escape_8bit.sub(b'', results[0]).strip()
        return results

    def _intercept_cmd(self, _bytes):
        try:
            self._intercept_recv = True
            self._repl._write_bytes(_bytes)
            _bytes = self._recv_intercepted()
            if self._is_cmd:
                results = self._post_process_intercept_cmd_win(_bytes)
                self._repl._write_bytes(b'\x1b')
            else:
                results = self._post_process_intercept_cmd_unix(_bytes)
        except Exception as e:
            results = None
            print('error in Interceptor')
            print(e)
        finally:
            self._intercept_recv = False
            try:
                self._recv_Q.get_nowait()
            except Empty:
                pass
            with self._recv_Q.mutex:
                self._recv_Q.queue.clear()
        return results

    def _get_cwd(self):
        msg = b'pwd\n'
        results = self._intercept_cmd(msg)
        if not results:
            return None
        _bytes = results[0]
        if b'/' not in _bytes:
            return None
        index = _bytes.index(b'/')
        cwd = _bytes[index:].decode()
        if '\n' in cwd:
            index = cwd.index('\n')
            cwd = cwd[:index]
        cwd = cwd.strip()
        return cwd

    def _get_user(self):
        msg = f'echo $USER\n'.encode()
        results = self._intercept_cmd(msg)
        if not results:
            return None
        _bytes = results[0]
        user = _bytes.decode()
        return user

    def _get_file(self, path):
        filename = os.path.basename(path)
        out_path = os.path.join(self._sftp_directory, filename).replace('\\', '/')
        try:
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with self._repl._client.open_sftp() as sftp:
                sftp.get(path, out_path)
        except IOError:
            with open(out_path, 'w'):
                pass
        except Exception as e:
            print(e)
            return
        return out_path

    def _process_vi(self, _bytes):
        if not _bytes.startswith(b'vi '):
            return False
        path = _bytes[3:].strip().decode()
        if path.startswith('./'):
            path = path[2:]
        elif path.startswith('~'):
            user = self._get_user()
            if not user:
                return True
            path = f'/home/{user}{path[1:]}'.replace('\\','/')
        if not path.startswith('/'):
            parent = self._get_cwd()
            if parent is None:
                return True
            path = os.path.join(parent, path).replace('\\','/')
        out_path = self._get_file(path)
        if out_path is not None:
            view = sublime.active_window().open_file(out_path)
            view.settings().set('SublimeREPL-ssh-sftp', True)
            view.settings().set('SublimeREPL-ssh-sftp.src_path', out_path)
            view.settings().set('SublimeREPL-ssh-sftp.dest_path', path)
            view.settings().set('view_repl_id', self._repl.id)
        return True

    @staticmethod
    def _common_prefix(words):
        if not words:
            return b""
        
        min_length = min(len(word) for word in words)
        prefix = b""
        for i in range(min_length):
            letter = words[0][i:i+1]
            if all(word.startswith(prefix + letter) for word in words):
                prefix += letter
            else:
                break
        return prefix

    def _process_tab_win(self, text):
        msg = f'{text}\t'.encode()
        results = self._intercept_cmd(msg)
        if not results or len(results) != 1:
            return True, None
        txt = results[0].decode()
        return True, txt

    def _process_tab_unix(self, text):
        text_rsplit = text.rsplit(maxsplit=1)
        if not len(text_rsplit):
            return False, None
        word = text_rsplit[-1]
        if len(text_rsplit) == 1:
            prefix = ""
        else:
            prefix = f'{text_rsplit[0]} '
        msg = f'compgen -f {word}\n'.encode()
        results = self._intercept_cmd(msg)
        if not results:
            return True, None
        if len(results) == 1:
            result = results[0]
        else:
            result = self._common_prefix(results)
        txt = f'{prefix}{result.decode()}'
        return True, txt

    def _process_tab(self, text):
        if self._is_cmd:
            ret, txt = self._process_tab_win(text)
        else:
            ret, txt = self._process_tab_unix(text)
        if ret and txt is not None:
            view = sublime.active_window().active_view()
            view.run_command('repl_escape')
            view.run_command("repl_insert_text", {"pos": view.size(), "text": txt})
        return ret

    def attach(self, repl):
        self._repl = repl
        self._repl.read_bytes = self._read_bytes
        self._repl.write_bytes = self._write_bytes
        self._recv_Q = Queue(maxsize=1)
        self._recv_return_Q = Queue(maxsize=1)

    def put_file(self, src_path, dest_path):
        try:
            with self._repl._client.open_sftp() as sftp:
                sftp.put(src_path, dest_path)
        except Exception as e:
            print(e)

    def process(self, _bytes):
        if self._is_intercept_vi:
            ret = self._process_vi(_bytes)
            if ret:
                return True
        return False
