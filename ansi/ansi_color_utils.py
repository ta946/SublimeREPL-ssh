import sublime

import os
import json
import re
import types

comment_regex = re.compile(r'\/\/.*$\r?\n?', re.MULTILINE)
comma_regex = re.compile(r',(\s*[\]|}])', re.MULTILINE)


def _sanitize_json_quotes_comments_commas(text):
    text = text.replace("'", '"')
    text = comment_regex.sub('', text)
    text = comma_regex.sub(r'\1', text)
    return text

def _get_color_scheme_rules(color_schema_text):
    color_schema_text = _sanitize_json_quotes_comments_commas(color_schema_text)
    color_scheme_json = json.loads(color_schema_text)
    variables = color_scheme_json.get('variables', {})
    for k, v in variables.items():
        find_text = f"var({k})"
        color_schema_text = color_schema_text.replace(find_text, v)
    color_scheme_json = json.loads(color_schema_text)
    rules = color_scheme_json.get('rules', [])
    return rules

def _set_color_scheme(self):
    self._view.settings().set("color_scheme", f"Packages/{self._cs_file_relative}")

def _cleanup_ansi_color(self, *args):
    try:
        color_scheme = self._view.settings().get("color_scheme")
        session_path = os.path.join(os.getenv('APPDATA'), 'Sublime Text', 'Local', 'Auto Save Session.sublime_session')
        with open(session_path, 'r') as f:
            text = f.read()
        text.replace(f'"color_scheme": {color_scheme},', '')
        with open(session_path, 'w') as f:
            f.write(text)
    except Exception as e:
        print(e)
    self._view.settings().erase("color_scheme")
    if os.path.exists(self._cs_file):
        os.remove(self._cs_file)

def init_ansi_color(self):
    self._set_color_scheme = types.MethodType(_set_color_scheme, self)
    self._cleanup_ansi_color = types.MethodType(_cleanup_ansi_color, self)
    self._cs_file_relative = f"User/SublimeREPL-ssh/{self.repl.id}.sublime-color-scheme"
    self._cs_file = os.path.join(sublime.packages_path(), self._cs_file_relative)
    rules = []
    try:
        color_scheme_path = self._view.style_for_scope("source_file")['source_file']
        if color_scheme_path.startswith('Packages'):
            color_scheme_path = color_scheme_path[len('Packages')+1:]
            color_scheme_path = os.path.join(sublime.packages_path(), color_scheme_path)
        with open(color_scheme_path, 'r') as f:
            color_schema_text = f.read()
        rules = _get_color_scheme_rules(color_schema_text)
    except Exception as e:
        print(e)
    color_scheme = {
        "author": "Auto-generated by SublimeREPL-ssh plugin",
        "globals": self._view.style(),
        "name": "AnsiColor",
        "rules": rules,
    }
    os.makedirs(os.path.dirname(self._cs_file), exist_ok=True)
    with open(self._cs_file,'w') as f:
        json.dump(color_scheme, f)
    sublime.set_timeout(self._set_color_scheme, 500)
    self.call_on_close.append(self._cleanup_ansi_color)