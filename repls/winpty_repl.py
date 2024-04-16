try:
    from winpty import PtyProcess
except (ImportError,ModuleNotFoundError):
    pass

import signal
import re

from ..sublimerepl import TERMINAL_HEIGHT
from .subprocess_repl import SubprocessRepl
from ..interceptor.interceptor import Interceptor


class WinptyRepl(SubprocessRepl):
    TYPE = "winpty"
    _ansi_os_control = re.compile(br'\x1b\]0;(.*)?\x07')

    def __init__(self, *args, cygwin=False, terminal_height=TERMINAL_HEIGHT, interceptor_handler=None, **kwargs):
        self._terminal_height = terminal_height
        super().__init__(*args, **kwargs)
        self._is_cygwin = bool(cygwin)
        self._interceptor_handler = interceptor_handler or Interceptor(intercept_vi=False, is_cmd=not self._is_cygwin)
        self._interceptor_handler.attach(self)

    def _open(self, settings, cwd, env):
        self.proc = PtyProcess.spawn(
            self._cmd,
            cwd=self.cwd(cwd, settings),
            env=env,
            dimensions=(self._terminal_height, 4096),
        )

    def is_alive(self):
        ret = self.proc.isalive()
        return ret

    def _read(self):
        # _bytes = self.proc.read(self._read_buffer).encode('utf-8')
        _bytes = self.proc.fileobj.recv(self._read_buffer)
        if not _bytes:
            self.proc.flag_eof = True
            return None
        if _bytes == b'0011Ignore':
            _bytes = b''
        return _bytes

    def _post_process(self, _bytes):
        _bytes = _bytes.replace(b'\r\n',b'\n')
        # if self._is_cygwin:
        _bytes = self._ansi_os_control.sub(b'', _bytes)
        return _bytes

    def _write_bytes(self, _bytes):
        # print('write_bytes',_bytes)
        text = _bytes.decode('utf-8')
        text = text.replace('\r\n','\n')
        if not self._is_cygwin:
            text = text.replace('\n','\r\n')
        self.proc.write(text)

    def write_bytes(self, _bytes):
        self._write_bytes(_bytes)

    def kill(self):
        self._killed = True
        self.proc.terminate()

    def send_signal(self, sig):
        code = b'\x04' if sig in ('EOT', b'\x04') else b'\x03'
        self.write_bytes(code)
        if sig == signal.SIGTERM:
            self._killed = True
            if self.is_alive():
                self.proc.sendintr()
        self._rv.clear_queue()
