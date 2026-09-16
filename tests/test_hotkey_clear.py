"""Clear a binding through the menu, persist it and assign it again."""
import json
import os
from pathlib import Path
import queue
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
import pygame
import commands
import hotkeys
import settings_io
from test_ui_buttons import build, paint, find
from test_config_atomic import GOOD


def main():
    empty = {entry[2]: '' for entry in hotkeys.DEFAULT_BINDINGS.values()}
    assert hotkeys.build_bindings(empty) == {}
    assert hotkeys.describe({}) == '' and hotkeys.numlock_needed({}) == []
    assert hotkeys.HotkeyController(queue.Queue(), {})._bindings == {}
    assert hotkeys.build_bindings({'toggle': 'invalid'}) == hotkeys.build_bindings()
    pygame.init()
    try:
        menu = build();menu.page = 'settings';menu.settings_tab = 'keys'
        menu.set_hotkeys(settings_io.hotkey_labels(hotkeys.build_bindings()))
        menu.layout(3840, 2160);paint(menu)
        row = find(menu, 'hotkey', 'toggle')
        pos = row.extra['clear'].center
        actions = menu.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))
        menu.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1))
        assert actions == [('hotkey', 'toggle', ''), ('capture', None)], actions
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'config.json';path.write_text(json.dumps(GOOD))
            st = SimpleNamespace(cfg={},cfg_path=path,lang='en',hotkeys=Mock(),
                                 display=SimpleNamespace(menu=menu,alert=Mock()))
            for action in actions:commands.apply_menu_action(st, action)
            assert menu.capturing is None
            st.hotkeys.resume.assert_called_once()
            assert json.loads(path.read_text())['hotkeys']['toggle'] == ''
            loaded = settings_io.load_config(path)
            assert not any(b[2] == 'toggle' for b in hotkeys.build_bindings(loaded['hotkeys']).values())
            assert 'toggle' not in menu.hotkeys
            commands.apply_menu_action(st, ('hotkey', 'toggle', 'Ctrl+Alt+F6'))
            loaded = settings_io.load_config(path)
            assert any(b[2:] == ('toggle','Ctrl+Alt+F6') for b in hotkeys.build_bindings(loaded['hotkeys']).values())
    finally:pygame.quit()
    print('PASS: clear button, persistence, reassign, invalid fallback and all bindings disabled')


if __name__ == '__main__':main()
