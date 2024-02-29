import re

try:
    from .ansi_regex import ANSI_ESCAPE_8BIT_REGEX, ANSI_ESCAPE_ALLOWCOLOR_REGEX
    from .ansi_color import AnsiColor
    from .ansi_sublime_regions import AnsiSublimeRegions
except ImportError:
    from ansi_regex import ANSI_ESCAPE_8BIT_REGEX, ANSI_ESCAPE_ALLOWCOLOR_REGEX
    from ansi_color import AnsiColor


class AnsiControl:
    def __init__(self, rv, is_ansi_allow_color=False):
        self.rv = rv
        self._cursor_pos = 0  # 1-indexed
        self._ansi_csi_regex_str = r'\x1b\[(\??\d*[;|\d*]*)((?!m)[a-zA-Z])'
        self._carriage_return_str = r'\r'  # \x0d
        self._newline_regex_str = r'\n'  # \x0a
        self._cursor_regex_str = f'(?:{self._ansi_csi_regex_str}|{self._carriage_return_str})'
        self._cursor_w_newline_regex_str = f'(?:{self._ansi_csi_regex_str}|{self._carriage_return_str}|{self._newline_regex_str})'
        self._clear_regex_str = r'\x1b\[J\x00+'
        self._endash_regex_str = r'\xe2\x80\x93'
        self._ansi_csi_regex = re.compile(self._ansi_csi_regex_str)
        self._carriage_return = re.compile(self._carriage_return_str)
        self._newline_regex = re.compile(self._newline_regex_str)
        self._cursor_regex = re.compile(self._cursor_regex_str)
        self._cursor_w_newline_regex = re.compile(self._cursor_w_newline_regex_str)
        self._clear_regex = re.compile(self._clear_regex_str)
        self._endash_regex = re.compile(self._endash_regex_str)
        self._ansi_escape_8bit_regex = ANSI_ESCAPE_8BIT_REGEX
        self._ansi_escape_allowcolor_regex = ANSI_ESCAPE_ALLOWCOLOR_REGEX
        self._is_ansi_allow_color = bool(is_ansi_allow_color)
        self._ansi_escape_regex = self._ansi_escape_allowcolor_regex if self._is_ansi_allow_color else self._ansi_escape_8bit_regex
        self._ansi_color = AnsiColor()
        if is_ansi_allow_color:
            self._ansi_sublime_regions = AnsiSublimeRegions(self.rv)
        self._debug = False
        self._debug_file_handle = None

    def _get_text_end(self):
        pos = self.rv._output_end - self.rv._prompt_size
        return pos

    @staticmethod
    def _check_newline(m):
        ret = m[0] == '\n'
        return ret

    @staticmethod
    def _check_carriage_return(m):
        ret = m[0] == '\r'
        return ret

    @staticmethod
    def _check_cursor_move(m):
        ret = m[2] in ('A', 'B', 'C', 'D', 'H')
        return ret

    @staticmethod
    def _check_line_erase(m):
        ret = m[1] in ('','0','1','2') and m[2] == 'K'
        return ret

    @staticmethod
    def _check_display_erase(m):
        ret = m[1] in ('','0','1','2','3') and m[2] == 'J'
        return ret

    @staticmethod
    def _check_bracketed_paste(m):
        ret = m[1] in ('?2004') and m[2] in ('h','l')
        return ret

    def _find_line_start(self, view_text):
        """returns \n pos+1"""
        text = view_text[:self._cursor_pos]
        m = re.search(self._newline_regex, text[::-1])
        if not m:
            pos = 0
            return False, pos
        start = m.start()
        pos = len(text) - start
        return True, pos

    def _find_line_end(self, view_text):
        """returns \n pos"""
        text = view_text[self._cursor_pos:]
        m = re.search(self._newline_regex, text)
        if not m:
            pos = self._get_text_end()
            return False, pos
        start = m.start()
        pos = self._cursor_pos + start
        return True, pos

    def _check_cursor_moved(self):
        ret = self._cursor_pos != self._get_text_end()
        return ret

    def _move_line_up(self, view_text, num_move):
        offset = None
        for _ in range(num_move):
            ret, pos = self._find_line_start(view_text)
            if not ret:
                return
            if offset is None:
                offset = self._cursor_pos - pos
            self._cursor_pos = pos - 1
            ret, pos = self._find_line_start(view_text)
            self._cursor_pos = pos
        ret, pos = self._find_line_end(view_text)
        self._insert_space_to_offset(offset)

    def _move_line_down(self, view_text, num_move):
        ret, pos = self._find_line_start(view_text)
        offset = self._cursor_pos - pos
        for _ in range(num_move):
            ret, pos = self._find_line_end(view_text)
            if not ret:
                self._cursor_pos = pos
                self.insert('\n')
                # pos = self._cursor_pos
                continue
            self._cursor_pos = pos + 1
        self._insert_space_to_offset(offset)

    def _move_cursor_forward(self, view_text, num_move):
        ret, pos = self._find_line_end(view_text)
        new_pos = self._cursor_pos+num_move
        diff = pos-new_pos
        if diff < 0:
            self._cursor_pos = pos
            text = ' '*diff
            self._insert_overwrite(text)
        else:
            self._cursor_pos = new_pos

    def _move_cursor_backward(self, view_text, num_move):
        """
        CORRECT BEHAVIOUR IS WRAP AROUND
        self._cursor_pos -= num_move
        BUT DUE TO HTOP GOING BACK TOO MANY CHARS, LIMIT TO LINE START
        """
        ret, pos = self._find_line_start(view_text)
        new_pos = self._cursor_pos-num_move
        new_pos = max(pos, new_pos)
        self._cursor_pos = new_pos

    def _move_cursor_coordinate(self, view_text, code):
        code_split = code.split(';')
        if len(code_split) == 1:
            y = 0
            x = 0
        else:
            y,x = code_split
            if y == '':
                y = 0
            if x == '':
                x = 0
            y = int(y)
            x = int(x)
        self._cursor_pos = 0
        if y:
            self._move_line_down(view_text, y)
        if x:
            self._move_cursor_forward(view_text, x)

    def _process_prefix(self, text, m):
        start, end = m.span()
        prefix = text[:start]
        if len(prefix):
            self.insert(prefix)
        remaining = text[end:]
        return remaining

    def _process_newline(self):
        self._process_carriage_return()
        self._move_line_down(self.rv.get_view_text(), 1)

    def _process_carriage_return(self):
        view_text = self.rv.get_view_text()
        text = view_text[:self._cursor_pos + 1]
        ret, pos = self._find_line_start(text)
        self._cursor_pos = pos
        return ret

    def _process_cursor_move(self, m):
        view_text = self.rv.get_view_text()
        if m[2] == 'H':  # COORDINATE
            self._move_cursor_coordinate(view_text, m[1])
        else:
            num_move = int(m[1]) if len(m[1]) else 1
            if m[2] == 'A':  # UP
                self._move_line_up(view_text, num_move)
            elif m[2] == 'B':  # DOWN
                self._move_line_down(view_text, num_move)
            elif m[2] == 'C':  # FORWARD
                self._move_cursor_forward(view_text, num_move)
            elif m[2] == 'D':  # BACKWARD
                self._move_cursor_backward(view_text, num_move)

    def _process_line_erase(self, m):
        view_text = self.rv.get_view_text()
        if m[1] == '1':  # Start of line through cursor
            _, start = self._find_line_start(view_text)
            end = self._cursor_pos
        elif m[1] == '2':  # Start to end of line
            _, start = self._find_line_start(view_text)
            _, end = self._find_line_end(view_text)
        else:  # ('','0') Cursor to end of line
            start = self._cursor_pos
            _, end = self._find_line_end(view_text)
        self._erase(start, end)

    def _process_display_erase(self, m):
        if m[1] == '1':  # Start of display through cursor
            start = 0
            end = self._cursor_pos
        elif m[1] in ('2','3'):  # entire display
            start = 0
            end = self.rv._view.size()
        else:  # ('','0') Cursor to end of display
            start = self._cursor_pos
            end = self.rv._view.size()
        self._erase(start, end)

    def _process_bracketed_paste(self, m):
        if m[1] == 'h':  # Enable bracketed paste
            pass
        elif m[1] == 'l':  # Disable bracketed paste
            pass

    def _process_ansi(self, m):
        if self._check_newline(m):
            self._process_newline()
        elif self._check_carriage_return(m):
            self._process_carriage_return()
        elif self._check_cursor_move(m):
            self._process_cursor_move(m)
        elif self._check_line_erase(m):
            self._process_line_erase(m)
        elif self._check_display_erase(m):
            self._process_display_erase(m)
        elif self._check_bracketed_paste(m):
            self._process_bracketed_paste(m)

    def _erase(self, start, end):
        length = end - start
        if length <= 0:
            return
        self.rv._output_end -= length
        self.rv._view.run_command("repl_erase_text", {"start": start, "end": end})

    def _insert_append(self, text, pos, style=None):
        self.rv._output_end += len(text)
        self._cursor_pos += len(text)
        self.rv._view.run_command("repl_insert_text", {"pos": pos, "text": text})
        if self._is_ansi_allow_color and style is not None:
            self._ansi_sublime_regions.insert_append(pos, self._cursor_pos, style)

    def _insert_overwrite(self, text):
        view_text = self.rv.get_view_text()
        ret, pos = self._find_line_end(view_text)
        line_length = pos - self._cursor_pos
        overwrite_length = min(line_length,len(text))
        end = self._cursor_pos + overwrite_length
        self._erase(self._cursor_pos, end)
        self._insert_append(text, self._cursor_pos)

    def _insert_space_to_offset(self, offset):
        view_text = self.rv.get_view_text()
        ret, pos = self._find_line_end(view_text)
        if self._cursor_pos + offset > pos:
            n_spaces = self._cursor_pos + offset - pos
            self._cursor_pos = pos
            self._insert_append(' ' * n_spaces, self._cursor_pos)
        else:
            self._cursor_pos += offset

    def _insert(self, text, style=None):
        text = self._ansi_escape_regex.sub('', text)
        if self._debug and self._debug_file_handle:
            self._debug_file_handle.write(text)
        is_cursor_moved = self._check_cursor_moved()
        if is_cursor_moved:
            self._insert_overwrite(text)
            return
        self._insert_append(text, self._cursor_pos, style)

    def insert(self, text):
        if self._is_ansi_allow_color:
            ret, text_sections = self._ansi_color.run(text)
            for text_section in text_sections:
                txt, style = text_section
                self._insert(txt, style)
        else:
            self._insert(text)


    def run(self, text, debug=False):
        # print('ansicontrol text')
        # print(text)
        # print(text.encode())
        self._debug = debug
        if self._debug:
            import os
            import datetime
            debug_path = os.path.join(os.path.dirname(__file__), "debug.txt")
            self._debug_file_handle = open(debug_path, "a", encoding='utf-8')
            self._debug_file_handle.write(f"\n-----input raw----- {datetime.datetime.now().isoformat()}\n")
            self._debug_file_handle.write(text)
            self._debug_file_handle.write("\n-----output-----\n")

        _text = text
        _text = self._clear_regex.sub('\x1b[J', _text)
        _text = self._endash_regex.sub('-', _text)
        while True:
            if not len(_text):
                break
            regex = self._cursor_w_newline_regex if self._check_cursor_moved() else self._cursor_regex
            m = re.search(regex, _text)
            if m is None:
                break
            _text = self._process_prefix(_text, m)
            self._process_ansi(m)
        if len(_text):
            self.insert(_text)
        if self._is_ansi_allow_color:
            self._ansi_sublime_regions.update_color_scheme()

        if self._debug_file_handle:
            self._debug_file_handle.write("\n-----end-----\n")
            self._debug_file_handle.close()
            self._debug_file_handle = None

"""
https://notes.burke.libbey.me/ansi-escape-codes/
https://vt100.net/docs/vt510-rm/chapter4.html
\x1b[?2004l  # bracketed paste mode (h: on l: off)
??? newline without indent matching previous line??? cant remember
add newline to prompt if no newline before text before prompt
"""

def main():
    class MockView:
        def __init__(self, text=""):
            self._text = text
        def size(self):
            size = len(self._text)
            return size
        def _erase_text(self, args):
            start = args["start"]
            end = args["end"]
            self._text = self._text[:start]+self._text[end+1:]
        def _insert_text(self, args):
            pos = args["pos"]
            text = args["text"]
            self._text = self._text[:pos]+text+self._text[pos+1:]
        def run_command(self, command, args):
            if command == 'repl_erase_text':
                self._erase_text(args)
            elif command == 'repl_insert_text':
                self._insert_text(args)
            else:
                raise NotImplementedError(f'{command} {args}')
    class MockReplView:
        def __init__(self, view):
            self._view = view
            self._prompt_size = 0
            self._output_end = self._view.size()
        def get_view_text(self):
            text = self._view._text
            return text
    view_text = ''
    view = MockView(view_text)
    rv = MockReplView(view)
    handler = AnsiControl(rv=rv, is_ansi_allow_color=False)
    handler._cursor_pos = view.size()
    text = '\x1b[m\x0f3\x1b[0;1m\x0f[\x1b[0m\x0f                          0.0%\x1b[0;1m\x0f]\x1b[1B'
    handler.run(text)
    print(rv.get_view_text())
    return
if __name__ == '__main__':
    main()
