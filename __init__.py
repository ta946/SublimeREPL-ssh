from __future__ import absolute_import, unicode_literals, print_function, division
import sys

SETTINGS_FILE = 'SublimeREPL-ssh.sublime-settings'
CAN_USE_PARAMIKO = False
CAN_USE_WINPTY = False

if sys.platform.startswith('win'):
    try:
        import winpty,six,cffi,bcrypt,cryptography,pycparser,nacl,paramiko
        CAN_USE_PARAMIKO = True
        CAN_USE_WINPTY = True
    except (ImportError,ModuleNotFoundError):
        import sys
        import os
        import sublime
        import shutil
        def copytree(src, dst, symlinks=False, ignore=None):
            for item in os.listdir(src):
                s = os.path.join(src, item)
                d = os.path.join(dst, item)
                if os.path.isdir(s):
                    if os.path.exists(d):
                        try:
                            shutil.rmtree(d)
                        except PermissionError as e:
                            print(e)
                            continue
                    shutil.copytree(s, d, symlinks, ignore)
                else:
                    if os.path.exists(d):
                        try:
                            os.remove(d)
                        except PermissionError as e:
                            print(e)
                            continue
                    shutil.copy2(s, d)
        sublime_lib_p38 = os.path.join(sublime.packages_path(),'..','Lib','python38')
        copytree(os.path.join(os.path.dirname(__file__),'dependancies'), sublime_lib_p38)
        sublime_install_path = os.path.join(os.path.dirname(sys.executable),'python3.dll')
        try:
            shutil.copy2(os.path.join(os.path.dirname(__file__),'python3.dll'), sublime_install_path)
        except PermissionError as e:
            print(e)
        try:
            import six,cffi,bcrypt,cryptography,pycparser,nacl,paramiko
            CAN_USE_PARAMIKO = True
        except (ModuleNotFoundError,ImportError):
            pass

        try:
            import winpty
            CAN_USE_WINPTY = True
        except (ModuleNotFoundError,ImportError):
            pass
