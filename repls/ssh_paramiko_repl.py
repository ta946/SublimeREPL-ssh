import sublime
import sublime_plugin

import paramiko

from .repl import Repl
from ..sublimerepl import TERMINAL_HEIGHT
from ..ansi.ansi_regex import ANSI_ESCAPE_8BIT_REGEX_BYTES
from .subprocess_repl import SubprocessRepl
from ..interceptor.interceptor import Interceptor


class SshParamikoRepl(SubprocessRepl):
    TYPE = "ssh_paramiko"

    def __init__(self, encoding, user, ip, key, env=None, terminal_height=TERMINAL_HEIGHT, interceptor_handler=None, **kwds):
        Repl.__init__(self, encoding, **kwds)
        self._user = user
        self._ip = ip
        self._key = key
        self._env = env
        self._terminal_height = terminal_height
        self._interceptor_handler = interceptor_handler or Interceptor()
        self._client = None
        self._transport = None
        self._channel = None
        self._alive = False
        self._killed = False

        self._ansi_escape_8bit = ANSI_ESCAPE_8BIT_REGEX_BYTES
        self._interceptor_handler.attach(self)
        try:
            sublime.active_window().active_view().set_status('SublimeREPL-ssh', f'connecting to {ip}')
            self._connect()
        finally:
            sublime.active_window().active_view().erase_status('SublimeREPL-ssh')

    def autocomplete_available(self):
        return False

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
        self._channel.get_pty(height=self._terminal_height)
        self._channel.invoke_shell()

    def name(self):
        return f'{self._user}@{self._ip}'

    def is_alive(self):
        # self._alive = self._check_alive()
        return self._alive

    def _read(self):
        _bytes = self._channel.recv(self._read_buffer)
        return _bytes

    def _write_bytes(self, _bytes):
        try:
            self._channel.sendall(_bytes)
        except paramiko.SSHException:
            self._alive = False

    def write_bytes(self, _bytes):
        self._write_bytes(_bytes)

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

    def send_signal(self, sig):
        self._rv.clear_queue()
        code = b'\x04' if sig in ('EOT', b'\x04') else b'\x03'
        self.write_bytes(code)
