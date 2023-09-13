import re
from time import sleep

import signal
import paramiko

from .repl import Repl


class SshParamikoRepl(Repl):
    TYPE = "ssh_paramiko"

    def __init__(self, encoding, user, ip, key, env=None, **kwds):
        super().__init__(encoding, **kwds)
        self._user = user
        self._ip = ip
        self._key = key
        self._env = env
        self._client = None
        self._transport = None
        self._channel = None
        self._alive = False
        self._killed = False
        self._read_buffer = 4096

        self._ansi_escape_8bit = re.compile(br'(?:\x1B[@-Z\\-_]|[\x80-\x9A\x9C-\x9F]|(?:\x1B\[|\x9B)[0-?]*[ -/]*[@-~])')

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

    def read_bytes(self):
        while True:
            _bytes = self._channel.recv(self._read_buffer)
            if not _bytes:
                return
            if len(_bytes) == self._read_buffer:
                sleep(0.001)
            _bytes = _bytes.replace(b'\r',b'')
            _bytes = self._ansi_escape_8bit.sub(b'', _bytes)
            if _bytes:
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
