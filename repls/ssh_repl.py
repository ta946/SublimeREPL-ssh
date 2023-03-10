import os
import re

from .sublimeutop_repl import SubprocessRepl


if os.name == 'posix':
    POSIX = True
    import select
else:
    POSIX = False


class SshRepl(SubprocessRepl):
    TYPE = "ssh"
    _NEWLINE_BYTE = b'\n'
    _TERMINAL_BYTE = b'\x07'
    _TERMINAL_BYTES_AMAZON_LINUX = [b'\x1b',b'[',b'?',b'1',b'0',b'3',b'4',b'h']
    _TERMINAL_END_BYTES = [b'$',b' ']
    _EOF_BYTES = [b'\x1b',b']',b'0',b';']
    _PYTHON_BYTES = [b'>',b'>',b'>',b' ']
    _DOCKER_BYTES = [b'r',b'o',b'o',b't',b'@']
    _DOCKER_END_BYTES = [b'#',b' ']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._os_amazon_linux = False

    # def read(self):
    #     """Reads at least one decoded char of output"""
    #     while True:
    #         bs = self.read_bytes()
    #         if not bs:
    #             return None
    #         try:
    #             output = bs.decode()
    #             print(output)
    #         except Exception as e:
    #             output = "■"
    #             self.reset_decoder()
    #         if output:
    #             return output

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

    def _amazon_linux_remove_ansi_color(self, line):
        line = re.sub(b'\x1b\[38;5;\d{1,3}m', b'', line)
        line = re.sub(b'\x1b\[0m', b'', line)
        return line

    def _post_process_line(self, line):
        if self._os_amazon_linux:
            line = self._amazon_linux_remove_ansi_color(line)
        return line

    def read_bytes(self):
        out = self.popen.stdout
        if POSIX:
            while True:
                i, _, _ = select.select([out], [], [])
                if i:
                    return out.read(4096)
        else:
            byte_list = []
            while True:
                byte = self.popen.stdout.read(1)
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
