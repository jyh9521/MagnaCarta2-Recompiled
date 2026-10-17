"""Verify SDK guest-output readback artifacts, never visible-window acceptance."""
import hashlib
import re
from pathlib import Path
FAILURES={'path-invalid','presenter-null','sdk-readback-failed','dimensions-invalid','stride-invalid','data-limit','span-overflow','span-limit','data-short','file-open-failed','file-write-failed','file-close-failed'}

def parse_guest_output_capture(text,output,requested=False):
    result=dict(status='disabled'if not requested else'invalid_capture',attempt_verified=False,capture_verified=False,errors=[],visible_present_proof=False,scope='One public SDK latest-output GPU readback; may synchronize/perturb scheduling. RGB pixels are not a visible window, game first-frame or playability acceptance.')
    if not requested:return result
    try:
        lines=text.splitlines()
        if [x for x in lines if x.startswith('TITLE_WAIT_SDK')]!=['TITLE_WAIT_SDK parent_attested=1']:raise ValueError('SDK attestation')
        if [x for x in lines if x.startswith('TITLE_GUEST_OUTPUT_CAPTURE')]!=['TITLE_GUEST_OUTPUT_CAPTURE enabled=1 sdk_guard=1 configured=1']:raise ValueError('configuration')
        records=[x for x in lines if x.startswith('GUEST_OUTPUT_CAPTURE ')]
        timing=[x for x in lines if x.startswith('GUEST_OUTPUT_CAPTURE_TIMING ')]
        unknown=[x for x in lines if x.startswith('GUEST_OUTPUT_CAPTURE') and x not in records+timing]
        if len(records)!=1 or len(timing)!=1 or unknown:raise ValueError('unique capture/timing framing')
        def fields(line,strings):
            out={}
            for token in line.split()[1:]:
                k,sep,v=token.partition('=')
                if not sep or not v or k in out:raise ValueError('malformed field')
                if k in strings:out[k]=v;continue
                if not re.fullmatch('[0-9]{1,20}',v)or int(v)>=2**64:raise ValueError('number width')
                out[k]=int(v)
            return out
        row=fields(records[0],{'status','path'});t=fields(timing[0],set())
        if set(row)!={'requested','status','path','width','height','stride','data_bytes','rgb_bytes','nonblack_pixels','varied_pixels','sdk_readback'}or row['requested']!=1 or row['path']not in {'guest-output.ppm','-'}or row['sdk_readback']not in (0,1):raise ValueError('record contract')
        if set(t)!={'elapsed_ms','scheduling_perturbed','visible_present_proof'}or (t['scheduling_perturbed'],t['visible_present_proof'])!=(1,0):raise ValueError('timing contract')
        if row['width']>0xFFFFFFFF or row['height']>0xFFFFFFFF:raise ValueError('dimension width')
        if row['status']!='captured':
            if row['status']not in FAILURES:raise ValueError('unknown capture status')
            early=row['status']in {'path-invalid','presenter-null','sdk-readback-failed'}
            if early and (row['sdk_readback'] or any(row[k]for k in ['width','height','stride','data_bytes','rgb_bytes','nonblack_pixels','varied_pixels'])):raise ValueError('pre-readback failure statistics')
            if not early and row['sdk_readback']!=1:raise ValueError('readback success missing')
            if row['status']=='path-invalid' and row['path']!='-':raise ValueError('invalid path representation')
            if row['status']!='path-invalid' and row['path']!='guest-output.ppm':raise ValueError('fixed capture path')
            if not early:
                w,h,stride=row['width'],row['height'],row['stride'];maxbytes=256*1024**2;rowbytes=w*4
                if not 1<=w<=8192 or not 1<=h<=8192:validation='dimensions-invalid'
                elif stride<rowbytes:validation='stride-invalid'
                elif row['data_bytes']>maxbytes:validation='data-limit'
                elif h>1 and stride>((2**64-1)-rowbytes)//(h-1):validation='span-overflow'
                elif (h-1)*stride+rowbytes>maxbytes:validation='span-limit'
                elif (h-1)*stride+rowbytes>row['data_bytes']:validation='data-short'
                else:validation='valid'
                if row['status'].startswith('file-'):
                    if validation!='valid' or row['rgb_bytes']!=w*h*3 or max(row['nonblack_pixels'],row['varied_pixels'])>w*h:raise ValueError('file failure image contract')
                elif row['status']!=validation or any(row[k]for k in ['rgb_bytes','nonblack_pixels','varied_pixels']):raise ValueError('validation failure contract')

            result.update(status=row['status'],attempt_verified=True,record=row,timing=t);return result
        w,h=row['width'],row['height'];stride=row['stride']
        if row['path']!='guest-output.ppm' or row['sdk_readback']!=1 or not 1<=w<=8192 or not 1<=h<=8192 or stride<w*4 or not (h-1)*stride+w*4<=row['data_bytes']<=256*1024**2 or row['rgb_bytes']!=w*h*3:raise ValueError('image bounds/stride/size')
        path=Path(output)/row['path']
        if not path.is_file()or path.stat().st_size>256*1024**2:raise ValueError('missing/oversize artifact')
        raw=path.read_bytes();head=f'P6\n{w} {h}\n255\n'.encode('ascii')
        if not raw.startswith(head)or len(raw)!=len(head)+w*h*3:raise ValueError('PPM framing/length')
        pixels=memoryview(raw)[len(head):];first=bytes(pixels[:3]);nonblack=varied=0
        for i in range(0,len(pixels),3):
            p=pixels[i:i+3];nonblack+=bool(p[0]or p[1]or p[2]);varied+=p!=first
        if (nonblack,varied)!=(row['nonblack_pixels'],row['varied_pixels']):raise ValueError('pixel statistics disagreement')
        result.update(status='captured',attempt_verified=True,capture_verified=True,record=row,timing=t,path=str(path),sha256=hashlib.sha256(raw).hexdigest(),size=len(raw),nonblack_pixels=nonblack,varied_pixels=varied)
    except (ValueError,KeyError,TypeError,OSError)as exc:result['errors'].append(str(exc))
    return result
