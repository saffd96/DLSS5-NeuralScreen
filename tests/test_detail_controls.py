"""Sharpness persists, clamps invalid config, sends once and reaches the slider."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock,patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).resolve().parent))
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
import pygame
import commands
import protocol
import pipeline
import settings_io
from test_config_atomic import GOOD,_payload
from test_ui_buttons import build,paint,find,click

def main():
    assert pipeline._log_wanted("[detail] unavailable; keeping NR output")
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'config.json'
        for value,expected in [(None,0),('bad',0),(-1,0),(2,1),(3,1),(.4,.4),(float('nan'),0)]:
            path.write_text(json.dumps(dict(GOOD,detail_strength=value)))
            assert settings_io.load_config(path)['detail_strength']==expected
        cfg=dict(GOOD,detail_strength=1.0)
        path.write_text(json.dumps(cfg))
        assert settings_io.load_config(path)['detail_enabled'] is True
        cfg['detail_enabled']=True
        path.write_text(json.dumps(dict(cfg,**_payload(cfg))))
        assert settings_io.load_config(path)['detail_strength']==1.0
        assert settings_io.load_config(path)['detail_enabled'] is True
        cfg=dict(GOOD,detail_strength=.75,detail_enabled=False)
        path.write_text(json.dumps(dict(cfg,**_payload(cfg))))
        loaded=settings_io.load_config(path)
        assert loaded['detail_strength']==.75 and loaded['detail_enabled'] is False
    worker=SimpleNamespace(stdin=io.BytesIO());reader=Mock()
    protocol.sync_detail(worker,reader,.4)
    assert len(worker.stdin.getvalue())==protocol.struct.calcsize(protocol.FRAME_FMT)
    protocol.sync_detail(worker,reader,.4);reader.recv.assert_called_once()
    protocol.sync_detail(worker,reader,0);assert reader.recv.call_count==2
    protocol.sync_detail(worker,reader,2)
    size=protocol.struct.calcsize(protocol.FRAME_FMT)
    assert protocol.struct.unpack(protocol.FRAME_FMT,worker.stdin.getvalue()[-size:])[2]==100
    protocol.sync_detail(worker,reader,1,enabled=False)
    assert protocol.struct.unpack(protocol.FRAME_FMT,worker.stdin.getvalue()[-size:])[2]==0
    protocol.sync_detail(worker,reader,1,enabled=True)
    assert protocol.struct.unpack(protocol.FRAME_FMT,worker.stdin.getvalue()[-size:])[2]==100
    pygame.init()
    try:
        menu=build();menu.set_state({'detail_strength':.4,'detail_enabled':True,'lang':'ru','dlss_sr':False});menu.layout(3840,2160);paint(menu)
        assert find(menu,'slider','detail_strength') is not None
        menu.set_state({'dlss_sr':True});menu.layout(3840,2160);paint(menu)
        item=find(menu,'slider','detail_strength');assert item is not None and item.value==.4
        track=item.extra['track']
        position=(track.right-1,track.centery)
        actions=menu.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN,pos=position,button=1))
        menu.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP,pos=position,button=1))
        assert ('detail_strength',1.0) in actions, actions
        assert menu.state['detail_strength']==1.0
        menu.set_state({'dlss_sr':False});menu.layout(3840,2160);paint(menu)
        assert find(menu,'slider','detail_strength') is not None
        menu.set_state({'dlss_sr':True});menu.layout(3840,2160);paint(menu)
        assert find(menu,'slider','detail_strength').value==1.0
        st=SimpleNamespace(cfg={},lang='ru')
        with patch.object(settings_io,'save_menu_layout') as save:
            commands.apply_menu_action(st,('detail_strength',1.0))
            assert st.cfg['detail_strength']==1.0;save.assert_called_once_with(st)
        st.cfg['detail_enabled']=True
        with patch.object(settings_io,'save_menu_layout'):
            for enabled in (False,True):
                actions=click(menu,find(menu,'toggle','detail_enabled'))
                assert actions==[('toggle','detail_enabled')],actions
                commands.apply_menu_action(st,actions[0])
                assert st.cfg['detail_enabled'] is enabled
                assert st.cfg['detail_strength']==1.0
                menu.set_state(st.cfg);menu.layout(3840,2160);paint(menu)
                assert (find(menu,'slider','detail_strength') is not None)==enabled
    finally:pygame.quit()
    print('PASS: sharpness config, persistence, wire cache and UI')

if __name__=='__main__':main()
