import os

from .sublimeutop_repl import SubprocessRepl


if os.name == 'posix':
    POSIX = True
    import select
else:
    POSIX = False


class SshRepl(SubprocessRepl):
    TYPE = "ssh"
    _START_BYTE = b'\x1b'
    _END_BYTE = b'\x07'

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

    def read_bytes(self):
        out = self.popen.stdout
        if POSIX:
            while True:
                i, _, _ = select.select([out], [], [])
                if i:
                    return out.read(4096)
        else:
            byte_list = []
            EOL = False
            is_terminal_prefix = False
            while True:
                byte = self.popen.stdout.read(1)
                if byte == b'\r':
                    # f'in HACK, for \r\n -> \n translation on windows
                    # I tried universal_endlines but it was pain and misery! :'(
                    continue
                byte_list.append(byte)
                if not byte or byte == b'\n':
                    EOL = True
                elif byte_list[0] == self._START_BYTE and self._END_BYTE in byte_list:
                    if byte_list[-2] == b'$' and byte_list[-1] == b' ':
                        EOL = True
                        is_terminal_prefix = True
                if EOL:
                    line = b''.join(byte_list)
                    if is_terminal_prefix:
                        end_index = line.index(self._END_BYTE)
                        line = line[end_index+1:]
                    return line
