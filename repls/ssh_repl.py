import re
from time import sleep

from .subprocess_repl import SubprocessRepl


class SshRepl(SubprocessRepl):
    TYPE = "ssh"
    _TERMINAL_PREFIX_REGEX = b'\\x1b]0;(\S+@ip-\d{1,3}-\d{1,3}-\d{1,3}-\d{1,3}:[^$]+)\\x07(\\x1b\[01;\d{1,3}m\S+@ip-\d{1,3}-\d{1,3}-\d{1,3}-\d{1,3}.+\$)?'
    _terminal_prefix_regex_compiled = re.compile(_TERMINAL_PREFIX_REGEX)
    _TERMINAL_BYTES_AMAZON_LINUX_REGEX = b'\\x1b\[\?\d{1,4}[h|l]'
    _terminal_bytes_amazon_linux_regex_compiled = re.compile(_TERMINAL_BYTES_AMAZON_LINUX_REGEX)
    _TERMINAL_BYTES_AMAZON_LINUX_SUFFIX_REGEX = b'\[\S+@ip-\d{1,3}-\d{1,3}-\d{1,3}-\d{1,3} [^\]]+]\$ '
    _terminal_bytes_amazon_linux_suffix_regex_compiled = re.compile(_TERMINAL_BYTES_AMAZON_LINUX_SUFFIX_REGEX)
    # _ANSI_COLOR_REGEX = b'\x1b\[38;5;\d{1,3}m'
    # _ansi_color_regex_compiled = re.compile(_ANSI_COLOR_REGEX)
    _read_buffer = 4096
    _ansi_escape_8bit = re.compile(br'(?:\x1B[@-Z\\-_]|[\x80-\x9A\x9C-\x9F]|(?:\x1B\[|\x9B)[0-?]*[ -/]*[@-~])')

    def _remove_ansi_color(self, _bytes):
        # _bytes = self._ansi_color_regex_compiled.sub(b'', _bytes)
        _bytes = self._ansi_escape_8bit.sub(b'', _bytes)
        return _bytes

    def _post_process_line(self, line):
        line = line.replace(b'\r', b'')
        line = self._terminal_prefix_regex_compiled.sub(rb'\1$', line)
        line = self._remove_ansi_color(line)
        line = self._terminal_bytes_amazon_linux_regex_compiled.sub(b'', line)
        line = self._terminal_bytes_amazon_linux_suffix_regex_compiled.sub(b' ', line)
        return line

    def read_bytes(self):
        out = self.popen.stdout
        while True:
            _bytes = out.read1(self._read_buffer)
            if not _bytes:
                return
            if len(_bytes) == self._read_buffer:
                sleep(0.001)
            _bytes = self._post_process_line(_bytes)
            if _bytes:
                return _bytes

    def send_signal(self, sig):
        self.write_bytes(b'\x03')
