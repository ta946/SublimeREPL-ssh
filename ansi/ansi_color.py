import re


XTERM_COLORS_256 = [
    # '#000000', '#800000', '#008000', '#808000', '#000080', '#800080', '#008080', '#c0c0c0', # standard
    # '#808080', '#ff0000', '#00ff00', '#ffff00', '#0000ff', '#ff00ff', '#00ffff', '#ffffff', # standard
    '#000000', '#cd0000', '#00cd00', '#cdcd00', '#0000ee', '#cd00cd', '#00cdcd', '#e5e5e5', # 
    '#7f7f7f', '#ff0000', '#00ff00', '#ffff00', '#5c5cff', '#ff00ff', '#00ffff', '#ffffff', # 
    '#000000', '#00005f', '#000087', '#0000af', '#0000d7', '#0000ff', '#005f00', '#005f5f',
    '#005f87', '#005faf', '#005fd7', '#005fff', '#008700', '#00875f', '#008787', '#0087af',
    '#0087d7', '#0087ff', '#00af00', '#00af5f', '#00af87', '#00afaf', '#00afd7', '#00afff',
    '#00d700', '#00d75f', '#00d787', '#00d7af', '#00d7d7', '#00d7ff', '#00ff00', '#00ff5f',
    '#00ff87', '#00ffaf', '#00ffd7', '#00ffff', '#5f0000', '#5f005f', '#5f0087', '#5f00af',
    '#5f00d7', '#5f00ff', '#5f5f00', '#5f5f5f', '#5f5f87', '#5f5faf', '#5f5fd7', '#5f5fff',
    '#5f8700', '#5f875f', '#5f8787', '#5f87af', '#5f87d7', '#5f87ff', '#5faf00', '#5faf5f',
    '#5faf87', '#5fafaf', '#5fafd7', '#5fafff', '#5fd700', '#5fd75f', '#5fd787', '#5fd7af',
    '#5fd7d7', '#5fd7ff', '#5fff00', '#5fff5f', '#5fff87', '#5fffaf', '#5fffd7', '#5fffff',
    '#870000', '#87005f', '#870087', '#8700af', '#8700d7', '#8700ff', '#875f00', '#875f5f',
    '#875f87', '#875faf', '#875fd7', '#875fff', '#878700', '#87875f', '#878787', '#8787af',
    '#8787d7', '#8787ff', '#87af00', '#87af5f', '#87af87', '#87afaf', '#87afd7', '#87afff',
    '#87d700', '#87d75f', '#87d787', '#87d7af', '#87d7d7', '#87d7ff', '#87ff00', '#87ff5f',
    '#87ff87', '#87ffaf', '#87ffd7', '#87ffff', '#af0000', '#af005f', '#af0087', '#af00af',
    '#af00d7', '#af00ff', '#af5f00', '#af5f5f', '#af5f87', '#af5faf', '#af5fd7', '#af5fff',
    '#af8700', '#af875f', '#af8787', '#af87af', '#af87d7', '#af87ff', '#afaf00', '#afaf5f',
    '#afaf87', '#afafaf', '#afafd7', '#afafff', '#afd700', '#afd75f', '#afd787', '#afd7af',
    '#afd7d7', '#afd7ff', '#afff00', '#afff5f', '#afff87', '#afffaf', '#afffd7', '#afffff',
    '#d70000', '#d7005f', '#d70087', '#d700af', '#d700d7', '#d700ff', '#d75f00', '#d75f5f',
    '#d75f87', '#d75faf', '#d75fd7', '#d75fff', '#d78700', '#d7875f', '#d78787', '#d787af',
    '#d787d7', '#d787ff', '#d7af00', '#d7af5f', '#d7af87', '#d7afaf', '#d7afd7', '#d7afff',
    '#d7d700', '#d7d75f', '#d7d787', '#d7d7af', '#d7d7d7', '#d7d7ff', '#d7ff00', '#d7ff5f',
    '#d7ff87', '#d7ffaf', '#d7ffd7', '#d7ffff', '#ff0000', '#ff005f', '#ff0087', '#ff00af',
    '#ff00d7', '#ff00ff', '#ff5f00', '#ff5f5f', '#ff5f87', '#ff5faf', '#ff5fd7', '#ff5fff',
    '#ff8700', '#ff875f', '#ff8787', '#ff87af', '#ff87d7', '#ff87ff', '#ffaf00', '#ffaf5f',
    '#ffaf87', '#ffafaf', '#ffafd7', '#ffafff', '#ffd700', '#ffd75f', '#ffd787', '#ffd7af',
    '#ffd7d7', '#ffd7ff', '#ffff00', '#ffff5f', '#ffff87', '#ffffaf', '#ffffd7', '#ffffff',
    '#080808', '#121212', '#1c1c1c', '#262626', '#303030', '#3a3a3a', '#444444', '#4e4e4e',
    '#585858', '#626262', '#6c6c6c', '#767676', '#808080', '#8a8a8a', '#949494', '#9e9e9e',
    '#a8a8a8', '#b2b2b2', '#bcbcbc', '#c6c6c6', '#d0d0d0', '#dadada', '#e4e4e4', '#eeeeee'
]


class AnsiColor:
    def __init__(self):
        self._ansi_color_unsupported_regex_str = r'\x1b\[(0;)?[25689]m'
        self._ansi_color_regex_str = r'(?:\x1b\[([0-9;]*)m)+\x0f?'
        self._ansi_charset_regex_str = r'\x1b\[(|)]\w?'
        self._ansi_null_regex_str = r'\x00'
        self._ansi_color_regex = re.compile(self._ansi_color_regex_str, flags=re.IGNORECASE)
        self._ansi_color_unsupported_regex = re.compile(self._ansi_color_unsupported_regex_str, flags=re.IGNORECASE)
        self._ansi_charset_regex = re.compile(self._ansi_charset_regex_str, flags=re.IGNORECASE)
        self._ansi_null_regex = re.compile(self._ansi_null_regex_str, flags=re.IGNORECASE)
        self._style = self._default_style()
        self._style_changed = False

    def _default_style(self):
        style = {
            'bold': False,
            'italic': False,
            'underline': False,
            'fg': None,
            'bg': None,
        }
        return style

    @staticmethod
    def _xterm_color(code, bright=False):
        num = int(code[-1])
        if bright:
            num += 8
        if not (0 <= num <= 255):
            return None
        color = XTERM_COLORS_256[num]
        return color

    @staticmethod
    def _rgb_to_hex(r, g, b):
        return '#{:02x}{:02x}{:02x}'.format(r, g, b)

    def _decode_multi(self, idx, code_split):
        i = idx+1
        if i > len(code_split):
            return idx, None
        item = code_split[i]
        if item == '5':  # 256
            i1 = i+1
            if i1 > len(code_split):
                return i1, None
            n = int(code_split[i1])
            color = XTERM_COLORS_256[n]
            i2 = i1+1
            if i2 >= len(code_split):
                return i1, color
            item = code_split[i2]
            if item == '0':
                return i2, color
            else:
                return i1, color
        elif item == '2':  # rgb
            i1 = i+1
            if i1 >= len(code_split):
                return i, None
            r = code_split[i1]
            i2 = i1+1
            if i2 >= len(code_split):
                return i1, None
            g = code_split[i2]
            i3 = i2+1
            if i3 >= len(code_split):
                return i2, None
            b = code_split[i3]
            color = self._rgb_to_hex(r, g, b)
            item = code_split[i3]
            if item == '0':
                return i3, color
            else:
                return i2, color
        else:
            return idx, None

    def _decode(self, ansi_color_text):
        ret = False
        style = {
        }
        code_split = ansi_color_text.split(';')
        idx = 0
        while True:
            if idx >= len(code_split):
                break
            item = code_split[idx]
            if item in ('0','00') or len(code_split) == 1 and item == '':
                style = self._default_style()
                ret = True
            elif item in ('1','01'):
                style['bold'] = True
                ret = True
            elif item in ('3','03'):
                style['italic'] = True
                ret = True
            elif item in ('4','04'):
                style['underline'] = True
                ret = True
            elif item in ('7','07'):
                style['fg'] = self._xterm_color('0', style.get('bold',False))
                style['bg'] = self._xterm_color('7', style.get('bold',False))
                ret = True
            elif '30' <= item <= '37':
                style['fg'] = self._xterm_color(item, style.get('bold',False))
                ret = True
            elif '40' <= item <= '47':
                style['bg'] = self._xterm_color(item, style.get('bold',False))
                ret = True
            elif '90' <= item <= '97':
                style['fg'] = self._xterm_color(item, bright=True)
                ret = True
            elif '100' <= item <= '107':
                style['bg'] = self._xterm_color(item, bright=True)
                ret = True
            elif item == '38':
                multi = 'fg'
                idx, color = self._decode_multi(idx, code_split)
                if color is not None:
                    style[multi] = color
                    ret = True
                continue
            elif item == '48':
                multi = 'bg'
                idx, color = self._decode_multi(idx, code_split)
                if color is not None:
                    style[multi] = color
                    ret = True
                continue
            idx += 1
        return ret, style

    def run(self, text):
        # print('ansicolor text')
        # print(text)
        # print(text.encode())

        text = self._ansi_charset_regex.sub('', text)
        text = self._ansi_null_regex.sub('', text)

        if not self._style_changed and not self._ansi_color_regex.search(text):
            return False, [[text, None]]

        text = self._ansi_color_unsupported_regex.sub('\x1b[1m', text)

        text_sections = []
        while True:
            if not len(text):
                break
            m = self._ansi_color_regex.search(text)
            if not m:
                break
            start_index = m.start()
            prefix = text[:start_index]
            if len(prefix):
                style = self._style.copy() if self._style_changed else None
                text_sections.append([prefix, style])
            text = text[m.end():]

            ansi_color_text = m[1]
            ret, current_style = self._decode(ansi_color_text)
            if not ret:
                continue
            self._style.update(current_style)
            self._style_changed = self._style != self._default_style()
        if len(text):
            style = self._style.copy() if self._style_changed else None
            text_sections.append([text, style])
        return True, text_sections

"""
https://www.ditig.com/256-colors-cheat-sheet
https://www.tweaking4all.com/software/linux-software/xterm-color-cheat-sheet/
"""


def main():
    handler = AnsiColor()
    text = '\x1b[0;7m\x0f    PID USER      PRI  NI  VIRT   RES   SHR S CPU% MEM%\xc3\xa2-\xc2\xbd  TIME+  Command        \x1b[10;1H   2350 root       20   0 3034M  689M  158M S  0.0  4.4  0:21.37 /usr/local/bin/\x1b[11;4H\x1b[m\x0f3534 \x1b[0m\x0froot      \x1b[m\x0f 20   0 \x1b[0;1m\x0f3034M  689M  158M \x1b[m\x0fS  0.0  4.4  0:00.00 \x1b[0;1m\x0f/usr/local/bin/\x1b[12;4H\x1b[m\x0f9593 \x1b[0m\x0froot      \x1b[m\x0f 20   0 \x1b[0;1m\x0f3034M  689M  158M \x1b[m\x0fS  0.0  4.4  0:00.05 \x1b[0;1m\x0f/usr/local/bin/\x1b[13;3H\x1b[m\x0f10000 \x1b[0m\x0froot      \x1b[m\x0f 20   0 \x1b[0;1m\x0f3034M  689M  158M \x1b[m\x0fS  0.0  4.4  0:00.04 \x1b[0;1m\x0f/usr/local/bin/\x1b[14;3H\x1b[m\x0f13123 \x1b[0m\x0froot      \x1b[m\x0f 20   0 \x1b[0;1m\x0f3034M  689M  158M \x1b[m\x0fS  0.0  4.4  0:00.05 \x1b[0;1m\x0f/usr/local/bin/\x1b[15;3H'
    # text = '[m3534 [0mroot      [m 20   0 [0;1m3034M  689M  158M [mS  0.0  4.4  0:00.00 [0;1m/usr/local/bin/'
    # text = '\x1b[0;7m\x0f    PID USER      PRI  NI  VIRT   RES   SHR S CPU% MEM%-  TIME+  Command        '
    text = '\x00 \x00 \x00 \x00 \x00 \x00 \x00 \x00 \x00U\x00n\x00r\x00e\x00g\x00i\x00s\x00t\x00e\x00r\x00s\x00 \x00t\x00h\x00e\x00 \x00d\x00i\x00s\x00t\x00r\x00i\x00b\x00u\x00t\x00i\x00o\x00n\x00 \x00a\x00n\x00d\x00 \x00d\x00e\x00l\x00e\x00t\x00e\x00s\x00 \x00t\x00h\x00e\x00 \x00r\x00o\x00o\x00t\x00 \x00f\x00i\x00l\x00e\x00s\x00y\x00s\x00t\x00e\x00m\x00.\x00'
    text = 'total 100\ndrwxr-x---  8 ubuntu ubuntu  4096 Nov 20 15:59 \x1b[0m\x1b[01;34m.\x1b[0m\ndrwxr-xr-x  3 root   root    4096 Oct 13 12:35 \x1b[01;34m..\x1b[0m\n-rw-------  1 ubuntu docker 35709 Nov 20 15:59 .bash_history\n'
    text = 'type nginx_log.txt\n/docker-entrypoint.sh: /docker-entrypoint.d/ is not empty, will attempt to perform configuration\n/docker-entrypoint.sh: Looking for shell scripts in /docker-entrypoint.d/\n/docker-entrypoint.sh: Launching /docker-entrypoint.d/10-listen-on-ipv6-by-default.sh\n10-listen-on-ipv6-by-default.sh: info: Getting the checksum of /etc/nginx/conf.d/default.conf\n10-listen-on-ipv6-by-default.sh: info: /etc/nginx/conf.d/default.conf differs from the packaged version\n/docker-entrypoint.sh: Launching /docker-entrypoint.d/20-envsubst-on-templates.sh\n/docker-entrypoint.sh: Launching /docker-entrypoint.d/30-tune-worker-processes.sh\n/docker-entrypoint.sh: Configuration complete; ready for start up\n2023/10/30 07:21:36 [notice] 1#1: using the "epoll" event method\n2023/10/30 07:21:36 [notice] 1#1: nginx/1.24.0\n2023/10/30 07:21:36 [notice] 1#1: built by gcc 10.2.1 20210110 (Debian 10.2.1-6) \n2023/10/30 07:21:36 [notice] 1#1: OS: Linux 6.2.0-1014-aws\n2023/10/30 07:21:36 [notice] 1#1: getrlimit(RLIMIT_NOFILE): 1048576:1048576\n2023/10/30 07:21:36 [notice] 1#1: start worker processes\n2023/10/30 07:21:36 [notice] 1#1: start worker process 27\n2023/10/30 07:21:36 [notice] 1#1: start worker process 28\n2023/10/30 07:21:36 [notice] 1#1: start worker process 29\n2023/10/30 07:21:36 [notice] 1#1: start worker process 30\n10.0.0.2 - - [30/Oct/2023:07:22:20 +0000] "POST /slbg_ask_server HTTP/1.1" 200 74 "-" "okhttp/4.11.0" "124.171.237.88"\n10.0.0.2 - - [30/Oct/2023:07:22:21 +0000] "POST /slbg_ask_server HTTP/1.1" 200 74 "-" "okhttp/4.11.0" "49.205.144.67"\n10.0.0.2 - - [30/Oct/2023:07:22:23 +0000] "POST /register_user HTTP/1.1" 409 26 "-" "okhttp/4.11.0" "124.171.237.88"\n10.0.0.2 - - [30/Oct/2023:07:22:23 +0000] "POST /register_user HTTP/1.1" 409 26 "-" "okhttp/4.11.0" "49.205.144.67"\n10.0.0.2 - - [30/Oct/2023:07:22:23 +0000] "GET /profile HTTP/1.1" 200 394 "-" "okhttp/4.11.0" "124.171.237.88"\n10.0.0.2 - - [30/Oct/2023:07:22:23 +0000] "POST /tips HTTP/1.1" 200 3224 "-" "okhttp/4.11.0" "124.171.237.88"\n10.0.0.2 - - [30/Oct/2023:07:22:23 +0000] "POST /slbg_login HTTP/1.1" 200 32 "-" "okhttp/4.11.0" "124.171.237.88"\n10.0.0.2 - - [30/Oct/2023:07:22:23 +0000] "GET /profile HTTP/1.1" 200 393 "-" "okhttp/4.11.0" "49.205.144.67"\n10.0.0.2 - - [30/Oct/2023:07:22:24 +0000] "POST /tips HTTP/1.1" 200 3224 "-" "okhttp/4.11.0" "49.205.144.67"\n10.0.0.2 - - [30/Oct/2023:07:22:24 +0000] "POST /slbg_login HTTP/1.1" 200 32 "-" "okhttp/4.11.0" "49.205.144.67"\n10.0.0.2 - - [30/Oct/2023:07:22:56 +0000] "POST /slbg_add_video HTTP/1.1" 200 51 "-" "okhttp/4.11.0" "124.171.237.88"\n10.0.0.2 - - [30/Oct/2023:07:22:59 +0000] "POST /slbg_app_event HTTP/1.1" 400 33 "-" "okhttp/4.11.0" "124.171.237.88"\n10.0.0.2 - - [30/Oct/2023:07:22:59 +0000] "POST /slbg_app_event HTTP/1.1" 400 33 "-" "okhttp/4.11.0" "124.171.237.88"\n10.0.0.2 - - [30/Oct/2023:07:22:59 +0000] "POST /coaching HTTP/1.1" 200 2268 "-" "okhttp/4.11.0" "124.171.237.88"\n10.0.0.2 - - [30/Oct/2023:07:22:59 +0000] "POST /coaching HTTP/1.1" 200 2268 "-" "okhttp/4.11.0" "124.171.237.88"\n10.0.0.2 - - [30/Oct/2023:07:23:03 +0000] "POST /fs_start_analysis HTTP/1.1" 200 39 "-" "python-requests/2.31.0" "13.54.4.183"\n10.'
    text = "\033[0;48;5;202mserver: slinger_app_dev_202310\033[0m"
    ret, text_sections = handler.run(text)
    for a in text_sections:
        print(a)

if __name__ == '__main__':
    main()
