import sublime
import sublime_plugin

import os
import re
from queue import Queue, Empty
from time import sleep

import signal
import paramiko

from .repl import Repl
from ..sublimerepl import SETTINGS_FILE


SFTP_DIRECTORY = os.path.join(sublime.packages_path(), 'SublimeREPL-ssh/repls/sftp').replace('\\', '/')


class ViInterceptor:
    def __init__(self, sftp_directory=SFTP_DIRECTORY):
        self._sftp_directory = sftp_directory
        self._intercept_recv = False
        self.src_path = None
        self.dest_path = None

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
        ret = self.process_vi(_bytes)
        if ret:
            return
        try:
            self._repl._channel.sendall(_bytes)
        except paramiko.SSHException:
            self._repl._alive = False

    def _get_cwd(self):
        cwd = ''
        try:
            self._intercept_recv = True
            msg = b'pwd\n'
            self._repl._channel.sendall(msg)
            _bytes = b''
            for _ in range(5):
                _bytes = self._recv_Q.get()
                if b'/' in _bytes:
                    break
            if b'/' not in _bytes:
                return None
            index = _bytes.index(b'/')
            cwd = _bytes[index:].decode()
            if '\n' in cwd:
                index = cwd.index('\n')
                cwd = cwd[:index]
            cwd = cwd.strip()
        finally:
            self._intercept_recv = False
            try:
                self._recv_Q.get_nowait()
            except Empty:
                pass
            with self._recv_Q.mutex:
                self._recv_Q.queue.clear()
        return cwd

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

    def process_vi(self, _bytes):
        if not _bytes.startswith(b'vi '):
            return False
        path = _bytes[3:].strip().decode()
        if path.startswith('./'):
            path = path[2:]
        if not path.startswith('/'):
            parent = self._get_cwd()
            if parent is None:
                return True
            path = os.path.join(parent, path).replace('\\','/')
        out_path = self._get_file(path)
        if out_path is not None:
            self.src_path = out_path
            self.dest_path = path
            view = sublime.active_window().open_file(out_path)
            view.settings().set('SublimeREPL-ssh-sftp', True)
        return True

vi_interceptor = ViInterceptor()


class SublimeReplsshViewEventListener(sublime_plugin.ViewEventListener):
    @classmethod
    def is_applicable(cls, settings):
        return settings.get('SublimeREPL-ssh-sftp')

    # def on_post_save(self):
    def on_post_save_async(self):
        global vi_interceptor
        if vi_interceptor.dest_path is None or vi_interceptor.src_path is None:
            return
        self.view.set_status('SublimeREPL-ssh', f'uploading {vi_interceptor.dest_path}...')
        vi_interceptor.put_file(vi_interceptor.src_path, vi_interceptor.dest_path)
        self.view.set_status('SublimeREPL-ssh', f'uploaded {vi_interceptor.dest_path}')

    def on_close(self):
        global vi_interceptor
        self.view.erase_status('SublimeREPL-ssh')
        vi_interceptor.src_path = None
        vi_interceptor.dest_path = None
        path = self.view.file_name()
        if os.path.exists(path):
            os.remove(path)


class SshParamikoRepl(Repl):
    TYPE = "ssh_paramiko"

    def __init__(self, encoding, user, ip, key, env=None, vi_interceptor_handler=None, **kwds):
        super().__init__(encoding, **kwds)
        self._user = user
        self._ip = ip
        self._key = key
        self._env = env
        self._vi_interceptor_handler = vi_interceptor_handler or vi_interceptor
        self._client = None
        self._transport = None
        self._channel = None
        self._alive = False
        self._killed = False
        self._read_buffer = 4096

        self._ansi_escape_8bit = re.compile(br'(?:\x1B[@-Z\\-_]|[\x80-\x9A\x9C-\x9F]|(?:\x1B\[|\x9B)[0-?]*[ -/]*[@-~])')

        settings = sublime.load_settings(SETTINGS_FILE)
        if settings.get("paramiko_intercept_vi"):
            self._vi_interceptor_handler.attach(self)
        self._connect()

    def _check_alive(self):
        try:
            if not self._transport.is_active():
                return False
            self._transport.send_ignore()
        except:
            return False
        return True
    
    def _connect(self):
        pkey = paramiko.RSAKey.from_private_key_file(self._key)
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._client.connect(hostname=self._ip, username=self._user, pkey=pkey)
        self._transport = self._client.get_transport()
        self._killed = False
        self._alive = self._check_alive()
        if not self._alive:
            raise RuntimeError(f"ssh_paramiko could not connect to {self._ip}")
        self._connect_channel()

    def _connect_channel(self):
        self._channel = self._transport.open_session()
        if self._env:
            self._channel.update_environment(self._env)
        self._channel.get_pty()
        self._channel.invoke_shell()

    def name(self):
        return f'{self._user}@{self._ip}'

    def is_alive(self):
        # self._alive = self._check_alive()
        return self._alive

    def _recv(self):
        _bytes = self._channel.recv(self._read_buffer)
        if not _bytes:
            return False, None
        if len(_bytes) == self._read_buffer:
            sleep(0.001)
        _bytes = _bytes.replace(b'\r',b'')
        _bytes = self._ansi_escape_8bit.sub(b'', _bytes)
        return True, _bytes

    def read_bytes(self):
        while True:
            ret, _bytes = self._recv()
            if not ret:
                return
            elif _bytes:
                return _bytes

    def write_bytes(self, _bytes):
        try:
            self._channel.sendall(_bytes)
        except paramiko.SSHException:
            self._alive = False

    def available_signals(self):
        signals = {}
        for k, v in list(signal.__dict__.items()):
            if not k.startswith("SIG") and k not in ['CTRL_C_EVENT','CTRL_BREAK_EVENT']:
                continue
            signals[k] = v
        return signals

    def send_signal(self, sig):
        self.write_bytes(b'\x03')

    def kill(self):
        self._killed = True
        self._alive = False
        try:
            self._channel.close()
        except:
            pass
        try:
            self._transport.close()
        except:
            pass
        try:
            self._client.close()
        except:
            pass
