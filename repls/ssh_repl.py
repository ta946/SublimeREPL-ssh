import re

from .subprocess_repl import SubprocessRepl
from ..ansi.ansi_regex import ANSI_ESCAPE_8BIT_REGEX_BYTES


class SshRepl(SubprocessRepl):
    TYPE = "ssh"
    _TERMINAL_PREFIX_REGEX = b'\\x1b]0;(\S+@ip-\d{1,3}-\d{1,3}-\d{1,3}-\d{1,3}:[^$]+)\\x07(\\x1b\[01;\d{1,3}m\S+@ip-\d{1,3}-\d{1,3}-\d{1,3}-\d{1,3}.+\$)?'
    _terminal_prefix_regex_compiled = re.compile(_TERMINAL_PREFIX_REGEX)
    # _TERMINAL_BYTES_AMAZON_LINUX_REGEX = b'\\x1b\[\?\d{1,4}[h|l]'
    # _terminal_bytes_amazon_linux_regex_compiled = re.compile(_TERMINAL_BYTES_AMAZON_LINUX_REGEX)
    _TERMINAL_BYTES_AMAZON_LINUX_SUFFIX_REGEX = b'\[\S+@ip-\d{1,3}-\d{1,3}-\d{1,3}-\d{1,3} [^\]]+]\$ '
    _terminal_bytes_amazon_linux_suffix_regex_compiled = re.compile(_TERMINAL_BYTES_AMAZON_LINUX_SUFFIX_REGEX)
    _read_buffer = 4096
    _ansi_escape_8bit = ANSI_ESCAPE_8BIT_REGEX_BYTES


    def _post_process(self, _bytes):
        _bytes = _bytes.replace(b'\r\n', b'\n')
        _bytes = self._terminal_prefix_regex_compiled.sub(rb'\1$', _bytes)
        # _bytes = self._ansi_escape_8bit.sub(b'', _bytes)
        # _bytes = self._terminal_bytes_amazon_linux_regex_compiled.sub(b'', _bytes)
        _bytes = self._terminal_bytes_amazon_linux_suffix_regex_compiled.sub(b' ', _bytes)
        return _bytes

    def send_signal(self, sig):
        self.write_bytes(b'\x03')
