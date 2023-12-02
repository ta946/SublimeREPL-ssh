import sublime
import json


class AnsiSublimeRegions:
    def __init__(self, rv):
        self.rv = rv
        self._styles = {}
        self._scopes_to_add = []

    def _erase_scope(self, scope):
        self.rv._view.erase_regions(scope)

    def insert_append(self, start, end, style):
        scope = f"{style['fg']}{style['bg']}"
        if scope not in self._styles:
            self._styles[scope] = style
            self._scopes_to_add.append(scope)
        region = sublime.Region(start,end)
        sum_regions = self.rv._view.get_regions(scope) + [region]
        self.rv._view.add_regions(
            scope, sum_regions, scope, "", sublime.DRAW_NO_OUTLINE | sublime.PERSISTENT
        )
        pass

    def update_color_scheme(self):
        if not len(self._scopes_to_add):
            return
        with open(self.rv._cs_file, 'r') as f:
            color_scheme = json.load(f)
        for scope in self._scopes_to_add:
            style = self._styles[scope]
            style_dict = {'scope': scope}
            if style['fg']:
                style_dict['foreground'] = style['fg']
            if style['bg']:
                bg = style['bg']
            else:
                background = color_scheme['globals']['background']
                if background[-1].lower() == 'f':
                    char = ord(background[-1])-1
                else:
                    char = ord(background[-1])+1
                bg = f'{background[:-1]}{chr(char)}'
            style_dict['background'] = bg
            color_scheme['rules'].append(style_dict)
        self._scopes_to_add = []
        with open(self.rv._cs_file, 'w') as f:
            json.dump(color_scheme, f)
        self.rv._view.settings().set('color_scheme', self.rv._view.settings().get('color_scheme'))

"""
handle overwrite regions
"""