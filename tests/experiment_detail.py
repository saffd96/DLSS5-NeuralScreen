"""Opt-in RTX readback and A/B timing for native-size SR bypass and sharpness."""
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import threading
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).resolve().parent))
import cv2
import numpy as np
import protocol as wire
from test_prepared_capture import exact


def source(w,h):
    image=np.full((h,w,4),255,np.uint8)
    image[:,:,:3]=40
    for y in range(45,h,70):
        cv2.putText(image,'Detail test: ABC 123 / thin text',(30,y),cv2.FONT_HERSHEY_SIMPLEX,.9,(225,225,225,255),1,cv2.LINE_AA)
    cv2.rectangle(image,(w//2,h//4),(w-45,3*h//4),(70,160,220,255),-1)
    return cv2.GaussianBlur(image,(5,5),.8)


def run(w,h,strength,sr=False,frames=55):
    folder=ROOT/'_work/detail-results';folder.mkdir(parents=True,exist_ok=True)
    tag=f'{w}x{h}-s{strength}-sr{int(sr)}-{time.time_ns()}'
    env=dict(os.environ,NS_HDR='0',NS_FRAMEGEN='0',NS_NR_SMALL='0')
    p=subprocess.Popen([str(ROOT/'native/nvngx.dll'),'--live'],cwd=ROOT/'native',env=env,
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
    logs=[];thread=threading.Thread(target=lambda:logs.extend(iter(p.stderr.readline,b'')),daemon=True);thread.start()
    watchdog=threading.Timer(120,p.kill);watchdog.start()
    image=source(w,h);motion=np.zeros((h,w,2),np.float16);timings=[];output=None
    def ack(fmt=wire.OUT_FMT):
        a=struct.unpack(fmt,exact(p.stdout,struct.calcsize(fmt)));assert a[2]==1,a;return a
    try:
        p.stdin.write(struct.pack(wire.HEADER_FMT,wire.VIDEO_MAGIC,w,h,1,0,0,0,1,0,0,0.,0.,0.,-1.,w,h));p.stdin.flush()
        for magic,value in ((wire.SR_SCALE_MAGIC,100),(wire.DETAIL_MAGIC,strength)):
            p.stdin.write(struct.pack(wire.FRAME_FMT,magic,0,value,0,0));p.stdin.flush();ack()
        for i in range(frames):
            start=time.perf_counter()
            wire.send_frame(p,i,image,motion,i==0,i,dlss_sr=sr)
            a=ack();assert a[3]==w*h*4,a
            pixels=exact(p.stdout,a[3]);elapsed=(time.perf_counter()-start)*1000
            if i>=10:timings.append(elapsed)
            if i==frames-1:output=np.frombuffer(pixels,np.uint8).reshape(h,w,4).copy()
        # Bypass is raw even with detail enabled.
        wire.send_frame(p,frames,image,motion,False,frames,bypass=True,dlss_sr=sr)
        a=ack();assert np.array_equal(np.frombuffer(exact(p.stdout,a[3]),np.uint8).reshape(h,w,4),image)
        p.stdin.close();p.wait(timeout=15);assert p.returncode==0,p.returncode
    finally:
        if p.poll() is None:p.kill();p.wait()
        watchdog.cancel();thread.join(timeout=2)
        (folder/(tag+'.log')).write_bytes(b''.join(logs))
    assert '[sr] ready:' not in b''.join(logs).decode('utf-8','replace'),'100% invoked DLSS'
    result=dict(width=w,height=h,strength=strength,sr=sr,mean_ms=float(np.mean(timings)),median_ms=float(np.median(timings)),p95_ms=float(np.percentile(timings,95)))
    cv2.imwrite(str(folder/(tag+'.png')),cv2.cvtColor(output,cv2.COLOR_RGBA2BGRA))
    print(result,flush=True)
    return output,result


def main():
    if '--run' not in sys.argv:raise SystemExit('Requires --run on Windows/NVIDIA')
    baseline,_=run(960,540,0,False,16)
    native,_=run(960,540,0,True,16)
    assert np.array_equal(baseline,native),'100% SR differs from normal NR'
    enhanced,_=run(960,540,50,True,16)
    assert np.array_equal(enhanced[:,:,3],baseline[:,:,3])
    assert np.any(enhanced[:,:,:3]!=baseline[:,:,:3]),'sharpness has no effect'
    assert np.abs(enhanced.astype(int)-baseline.astype(int)).max()<=16
    records=[]
    for strength in (0,50,50,0):
        _,record=run(2560,1440,strength,True);records.append(record)
    (ROOT/'_work/detail-results/timing.json').write_text(json.dumps(records,indent=2))
    print('PASS: 100% SR byte-exact NR, sharpness changes pixels, alpha and bypass preserved')


if __name__=='__main__':main()
