SublimeREPL-ssh (for windows)
=====================================

### Forked from [SublimeREPL](https://github.com/wuub/SublimeREPL). ([Original Readme](./README_original.md))

The purpose of this fork is to allow ssh repl for windows


### Limitations

This is not a terminal emulator, it just pushes the text you type through a subprocess running ssh then reads the response back.

* Any interactive terminal actions will not work. eg:
    * password entry
    * `ctrl+r` reverse search
    * `vi` for interactive file editing


### Getting started

* This method assumes you have ssh private keys `.pem` to connect to the server as password entry will not work!
* Before connecting to a server for the first time
    * you must ssh into the server using a regular terminal and type yes when `the authenticity of host can't be established` message appears to add the server to your `known_hosts` OR
    * create a file `C:\Users\<user>\.ssh\config` and add the line `StrictHostKeyChecking no`


### Keybindings to add

```
{
   "keys": [<user-defined keys>], "command": "repl_open", "args": {
        "cmd": {"windows": ["ssh", "-tt", "-i", <path_to_key.pem>, "<user>@<ip-address>"]},
        "cmd_postfix": "\n",
        "encoding": {"linux": "utf-8", "osx": "utf-8", "windows": "$win_cmd_encoding"},
        "env": {}, 
        "external_id": "shell",
        "suppress_echo": true,
        "syntax": "Packages/SublimeREPL-ssh/config/Io/Io.tmLanguage",
        "type": "ssh"
    },
    { "keys": ["shift+ctrl+c"], "command": "subprocess_repl_send_signal", "args": {"signal": "SIGTERM"},
        "context": [{ "key": "setting.repl", "operator": "equal", "operand": true }]
    }
}
```
