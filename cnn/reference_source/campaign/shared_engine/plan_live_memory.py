"""Versioned exact liveness allocator; preserves original full-program failure."""
import copy,json,re,shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
SOURCE=Path.home()/'fpga_builds/g2_shared_engine_20261017_r1'
BUILD=Path.home()/'fpga_builds/g2_shared_engine_20261017_live_r2'

def main():
    if BUILD.exists():raise RuntimeError('Versioned liveness build exists; inspect before retry')
    program=json.loads((SOURCE/'program.json').read_text());ops=program['instructions'];last={};sizes={0:288*384};input_size=sizes[0]
    for pc,op in enumerate(ops):
        sizes[op['o']]=((op['oc']+7)//8)*op['oh']*op['ow'];last[op['a']]=pc
        if op['kind'] in [2,3]:last[op['b']]=pc
    for head in program['heads']:last[head['offset_words']]=len(ops)
    for pc,op in enumerate(ops):last.setdefault(op['o'],pc)
    address={0:0};active={0};free=[];high=input_size;new=[];audit=[]
    def release(base,length):
        free.append((base,length));free.sort();merged=[]
        for a,n in free:
            if merged and merged[-1][0]+merged[-1][1]==a:merged[-1]=(merged[-1][0],merged[-1][1]+n)
            else:merged.append((a,n))
        free[:]=merged
    for pc,op in enumerate(ops):
        sources=[op['a']]+([op['b']] if op['kind'] in [2,3] else [])
        if any(source not in active for source in sources):raise RuntimeError('Source freed before final use')
        count=sizes[op['o']];slot=next((i for i,(_,n) in enumerate(free) if n>=count),None)
        if slot is None:base=high;high+=count
        else:
            base,length=free.pop(slot)
            if length>count:free.insert(slot,(base+count,length-count))
        for source in active:
            a=address[source];b=a+sizes[source]
            if max(a,base)<min(b,base+count):raise RuntimeError('Output overlaps still-live tensor')
        address[op['o']]=base;active.add(op['o']);r=copy.deepcopy(op);r.update(a=address[op['a']],o=base)
        if op['kind'] in [2,3]:r['b']=address[op['b']]
        new.append(r);released=[]
        for source in list(active):
            if last[source]==pc:
                active.remove(source);release(address[source],sizes[source]);released.append(source)
        audit.append({'instruction':pc,'output_old':op['o'],'output_new':base,'size_words':count,'released_old_tensors':released,'still_live_words':sum(sizes[x] for x in active)})
    BUILD.mkdir()
    for name in ['cnn_engine.cpp','cnn_engine.h','test_engine.cpp','coefficients.bin','input_0.bin','input_1.bin','input_2.bin']:shutil.copy2(SOURCE/name,BUILD/name)
    header=(SOURCE/'program.h').read_text();keys=['kind','a','b','o','ih','iw','ic','oh','ow','oc','k','s','p','wo','bo','q','relu','bc']
    header=re.sub(r'#define FEATURE_WORDS \d+',f'#define FEATURE_WORDS {high}',header)
    pattern=r'static const Op PROGRAM\[PROGRAM_LENGTH\]=\{.*?\n\};'
    replacement='static const Op PROGRAM[PROGRAM_LENGTH]={\n'+',\n'.join('{'+','.join(str(op[k]) for k in keys)+'}' for op in new)+'\n};'
    header,n=re.subn(pattern,lambda m:replacement,header,flags=re.S);assert n==1
    for i,head in enumerate(program['heads']):
        old=head['offset_words'];head['offset_words']=address[old];header=re.sub(r'#define HEAD'+str(i)+r'_OFFSET \d+',f'#define HEAD{i}_OFFSET {address[old]}',header)
    (BUILD/'program.h').write_text(header)
    before=program['feature_ddr_bytes'];program.update(instructions=new,feature_ddr_words=high,feature_ddr_bytes=high*16,
        memory_plan={'old_feature_ddr_bytes':before,'new_feature_ddr_bytes':high*16,'unchanged_arithmetic_coefficients_instruction_order':True,'live_interval_overlap_checks_passed':True,'full_numeric_recheck_required':True})
    (BUILD/'program.json').write_text(json.dumps(program,indent=2));(BUILD/'LIVENESS_AUDIT.json').write_text(json.dumps(audit,indent=2))
    original=(HERE/'run_shared_preflight.py').read_text();old="REPORT=HERE/'PREFLIGHT.json'"
    new_text="SOURCE=HERE;HERE=Path.home()/'fpga_builds/g2_shared_engine_20261017_live_r2'\nREPORT=SOURCE/'PREFLIGHT_LIVE_R2.json'"
    assert old in original;(HERE/'run_shared_live_r2.py').write_text(original.replace(old,new_text))
    print(json.dumps({'old_mib':before/2**20,'new_mib':high*16/2**20,'reduction_factor':before/(high*16),'build':str(BUILD)}))

if __name__=='__main__':main()
