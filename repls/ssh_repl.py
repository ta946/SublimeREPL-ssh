import os

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
    _TERMINAL_END_BYTES = [b'$',b' ']
    _EOF_BYTES = [b'\x1b',b']',b'0',b';']
    _PYTHON_BYTES = [b'>',b'>',b'>',b' ']
    _DOCKER_BYTES = [b'r',b'o',b'o',b't',b'@']
    _DOCKER_END_BYTES = [b'#',b' ']

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

    def _check_eol(self, byte_list):
        eol = False
        is_terminal_prefix = False

        if not byte_list[-1] or byte_list[-1] == self._NEWLINE_BYTE:
            eol = True
        elif self._ends_with(self._EOF_BYTES, byte_list):
            eol = True
        elif self._ends_with(self._TERMINAL_END_BYTES, byte_list) and self._TERMINAL_BYTE in byte_list:
            eol = True
            is_terminal_prefix = True
        elif self._ends_with(self._PYTHON_BYTES, byte_list):
            eol = True
        elif self._starts_with(self._DOCKER_BYTES, byte_list) and self._ends_with(self._DOCKER_END_BYTES, byte_list):
            eol = True
        return eol, is_terminal_prefix

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
                eol, is_terminal_prefix = self._check_eol(byte_list)
                if eol:
                    if is_terminal_prefix:
                        end_index = byte_list.index(self._TERMINAL_BYTE)
                        byte_list = byte_list[end_index+1:]
                    if len(byte_list) == len(self._EOF_BYTES) and byte_list == self._EOF_BYTES:
                        byte_list = []
                    elif self._ends_with(self._EOF_BYTES, byte_list):
                        byte_list = byte_list[:-len(self._EOF_BYTES)]+[b'\n']
                    if not len(byte_list):
                        continue
                    line = b''.join(byte_list)
                    return line

    def send_signal(self, sig):
        self.write_bytes(b'\x03')
