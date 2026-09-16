"""Optional effect bindings use the same actions as the menu switches."""
import json
import os
from pathlib import Path
import queue
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
import pygame
import commands
import hotkeys
import settings_io
from test_ui_buttons import build, paint, find
from test_config_atomic import GOOD


def main():
    names = set(hotkeys.OPTIONAL_BINDINGS.values())
    assert not names.intersection(b[2] for b in hotkeys.build_bindings().values())
    mapping = dict(zip(('dlss_sr', 'detail_enabled', 'boost'), ('F8', 'F9', 'F10')))
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp)/'config.json'
        path.write_text(json.dumps(dict(GOOD, hotkeys=mapping)))
        bindings = hotkeys.build_bindings(settings_io.load_config(path)['hotkeys'])
        assert {b[2]: b[3] for b in bindings.values() if b[2] in names} == mapping
        assert not names.intersection(b[2] for b in hotkeys.build_bindings(dict.fromkeys(names, '')).values())
    pygame.init()
    try:
        menu = build();menu.page='settings';menu.settings_tab='keys'
        menu.set_hotkeys(settings_io.hotkey_labels(bindings));menu.layout(3840,2160);paint(menu)
        for cmd in names:
            assert find(menu,'hotkey',cmd) is not None
        st = SimpleNamespace(cfg={'profile':'Natural','detail_strength':.7}, params={},
            nr_small=False,work_scale=.65,running=True,tray_commands=queue.Queue(),
            display=SimpleNamespace(menu=menu))
        with patch.object(settings_io,'save_menu_layout'), \
             patch.object(settings_io,'work_scale_cap',return_value=1.0), \
             patch.object(commands.pipeline,'request_apply') as apply:
            for _ in range(2):
                for cmd in ('dlss_sr','detail_enabled','boost'):st.tray_commands.put(cmd)
                assert commands.drain_commands(st)
            assert st.cfg['dlss_sr'] is False and st.cfg['detail_enabled'] is False
            assert st.cfg['detail_strength']==.7
            assert apply.call_count==2 and apply.call_args.kwargs['new_small'] is True
    finally:pygame.quit()
    print('PASS: optional assignments, persistence, clearing, UI rows and effect command dispatch')


if __name__=='__main__':main()
