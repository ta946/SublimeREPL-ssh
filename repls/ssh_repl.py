import os
import re
from time import sleep

from .subprocess_repl import SubprocessRepl


if os.name == 'posix':
    POSIX = True
    import select
else:
    POSIX = False


class SshRepl(SubprocessRepl):
    TYPE = "ssh"
    # _NEWLINE_BYTE = b'\n'
    # _TERMINAL_BYTES_AMAZON_LINUX = [b'\x1b',b'[',b'?',b'1',b'0',b'3',b'4',b'h']
    # _TERMINAL_END_BYTES = [b'$',b' ']
    # _EOF_BYTES = [b'\x1b',b']',b'0',b';']
    # _PYTHON_BYTES = [b'>',b'>',b'>',b' ']
    # _DOCKER_BYTES = [b'r',b'o',b'o',b't',b'@']
    # _DOCKER_END_BYTES = [b'#',b' ']
    _TERMINAL_BYTE = b'\x07'
    _TERMINAL_PREFIX_REGEX = b'\\x1b]0;(\S+@ip-\d{1,3}-\d{1,3}-\d{1,3}-\d{1,3}:[^$]+)\\x07(\\x1b\[01;\d{1,3}m\S+@ip-\d{1,3}-\d{1,3}-\d{1,3}-\d{1,3}.+\$)?'
    _terminal_prefix_regex_compiled = re.compile(_TERMINAL_PREFIX_REGEX)
    _TERMINAL_BYTES_AMAZON_LINUX_REGEX = b'\\x1b\[\?\d{1,4}[h|l]'
    _terminal_bytes_amazon_linux_regex_compiled = re.compile(_TERMINAL_BYTES_AMAZON_LINUX_REGEX)
    _TERMINAL_BYTES_AMAZON_LINUX_SUFFIX_REGEX = b'\[\S+@ip-\d{1,3}-\d{1,3}-\d{1,3}-\d{1,3} [^\]]+]\$ '
    _terminal_bytes_amazon_linux_suffix_regex_compiled = re.compile(_TERMINAL_BYTES_AMAZON_LINUX_SUFFIX_REGEX)
    _ANSI_COLOR_REGEX = b'\x1b\[38;5;\d{1,3}m'
    _ansi_color_regex_compiled = re.compile(_ANSI_COLOR_REGEX)
    _read_buffer = 4096

    def _starts_with(self, arr, byte_list):
        return byte_list[:len(arr)] == arr

    def _ends_with(self, arr, byte_list):
        return byte_list[-len(arr):] == arr

    def _list_at_index_contains(self, arr, byte_list, index):
        sublist = byte_list[index:index+len(arr)]
        return arr == sublist

    def _check_eol(self, byte_list):
        eol = False
        terminal_prefix_index = None

        if not byte_list[-1] or byte_list[-1] == self._NEWLINE_BYTE:
            eol = True
        elif self._ends_with(self._EOF_BYTES, byte_list):
            eol = True
        elif self._ends_with(self._TERMINAL_END_BYTES, byte_list) and self._TERMINAL_BYTE in byte_list:
            eol = True
            terminal_prefix_index = byte_list.index(self._TERMINAL_BYTE)
            if self._list_at_index_contains(self._TERMINAL_BYTES_AMAZON_LINUX, byte_list, terminal_prefix_index+1):
                self._os_amazon_linux = True
                terminal_prefix_index += len(self._TERMINAL_BYTES_AMAZON_LINUX)
        elif self._ends_with(self._PYTHON_BYTES, byte_list):
            eol = True
        elif self._starts_with(self._DOCKER_BYTES, byte_list) and self._ends_with(self._DOCKER_END_BYTES, byte_list):
            eol = True
        return eol, terminal_prefix_index

    def _remove_ansi_color(self, line):
        line = self._ansi_color_regex_compiled.sub(b'', line)
        return line

    def _post_process_line(self, line):
        line = line.replace(b'\r', b'')
        line = self._terminal_prefix_regex_compiled.sub(rb'\1$', line)
        line = self._remove_ansi_color(line)
        line = self._terminal_bytes_amazon_linux_regex_compiled.sub(b'', line)
        line = self._terminal_bytes_amazon_linux_suffix_regex_compiled.sub(b' ', line)
        return line

    def read_bytes(self):
        out = self.popen.stdout
        if POSIX:
            while True:
                i, _, _ = select.select([out], [], [])
                if i:
                    break
        res = out.read1(self._read_buffer)
        if len(res) == self._read_buffer:
            sleep(0.001)
        # print('res BEFORE')
        # print(res)
        res = self._post_process_line(res)
        # print('res AFTER')
        # print(res)
        return res

        byte_list = []
        while True:
            byte = out.read(1)
            if byte == b'\r':
                # f'in HACK, for \r\n -> \n translation on windows
                # I tried universal_endlines but it was pain and misery! :'(
                continue
            byte_list.append(byte)
            # print('byte_list')
            # print(byte_list)
            # print(b''.join(byte_list))
            eol, terminal_prefix_index = self._check_eol(byte_list)
            if eol:
                if terminal_prefix_index is not None:
                    byte_list = byte_list[terminal_prefix_index+1:]
                if len(byte_list) == len(self._EOF_BYTES) and byte_list == self._EOF_BYTES:
                    byte_list = []
                elif self._ends_with(self._EOF_BYTES, byte_list):
                    byte_list = byte_list[:-len(self._EOF_BYTES)]+[b'\n']
                if not len(byte_list):
                    continue
                line = b''.join(byte_list)
                # print('line before post process')
                # print(line)
                line = self._post_process_line(line)
                # print('line')
                # print(line)
                return line

    def send_signal(self, sig):
        self.write_bytes(b'\x03')
