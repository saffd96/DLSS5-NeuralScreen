"""Opt-in comparison using the official Real-ESRGAN NCNN portable release.

Requires an explicit --tools folder containing ncnn/ and natural.jpg (the
upstream inputs/0014.jpg example). Does not install dependencies or download.
Timings include PNG I/O and executable startup; not isolated model GPU timing.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import threading
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(Path(__file__).resolve().parent))
import cv2
import numpy as np
from experiment_detail import source


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tools',type=Path,required=True)
    args=parser.parse_args();tools=args.tools.resolve()
    folder=ROOT/'_work/restoration-results'/str(time.time_ns());folder.mkdir(parents=True)
    incoming=folder/'input';outgoing=folder/'output';incoming.mkdir();outgoing.mkdir()
    natural=cv2.imread(str(tools/'natural.jpg'));assert natural is not None
    natural=cv2.resize(natural,(640,360),interpolation=cv2.INTER_AREA)
    text=cv2.cvtColor(source(640,360),cv2.COLOR_RGBA2BGR)
    for i in range(4):cv2.imwrite(str(incoming/f'natural-{i}.png'),np.roll(natural,i*2,axis=1))
    cv2.imwrite(str(incoming/'text.png'),text)
    start=time.perf_counter()
    completed=[]
    with (folder/'ncnn.log').open('w') as log:
        p=subprocess.Popen([str(tools/'ncnn/realesrgan-ncnn-vulkan.exe'),'-i',str(incoming),'-o',str(outgoing),
                          '-m',str(tools/'ncnn/models'),'-n','realesrgan-x4plus','-s','4','-t','512','-g','0','-j','1:1:1','-f','png','-v'],
                         cwd=tools/'ncnn',stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                         creationflags=subprocess.CREATE_NO_WINDOW)
        watchdog=threading.Timer(240,p.kill);watchdog.start()
        try:
            for raw in iter(p.stdout.readline,b''):
                line=raw.decode('utf-8','replace');log.write(line)
                if 'done' in line.lower() and '.png' in line:completed.append(time.perf_counter()-start)
            p.wait();assert p.returncode==0,p.returncode
        finally:
            if p.poll() is None:p.kill();p.wait()
            watchdog.cancel()
    elapsed=time.perf_counter()-start
    names=list(outgoing.glob('*.png'));assert len(names)==5,names
    frames=[]
    for i in range(4):
        image=cv2.imread(str(outgoing/f'natural-{i}.png'));assert image.shape==(1440,2560,3)
        frames.append(cv2.resize(image,(640,360),interpolation=cv2.INTER_AREA))
    aligned=[float(np.abs(np.roll(frames[i],-i*2,axis=1).astype(float)[32:-32,32:-32]-frames[0][32:-32,32:-32]).mean()) for i in range(1,4)]
    restored_text=cv2.resize(cv2.imread(str(outgoing/'text.png')),(640,360),interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(folder/'native-size-natural-before-after.png'),np.concatenate((natural,frames[0]),axis=1))
    cv2.imwrite(str(folder/'native-size-text-before-after.png'),np.concatenate((text,restored_text),axis=1))
    result=dict(model='realesrgan-x4plus',runtime='official NCNN Vulkan 20220424',input='640x360',output='2560x1440',
                files=5,total_seconds=elapsed,batch_ms_per_file=elapsed*1000/5,
                native_size_aligned_mae=aligned, completed_offsets=completed,
                steady_batch_ms=((completed[-1]-completed[0])*1000/(len(completed)-1) if len(completed)>1 else None), limits='Includes executable startup and PNG I/O. No game FPS claim; one model/runtime only.')
    (folder/'result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2));print('Artifacts:',folder)


if __name__=='__main__':main()
