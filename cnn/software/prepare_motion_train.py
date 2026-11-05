import numpy as np

def geometry(proposal,image_shape,boxes):
    h,w=image_shape[:2];scale=640/w;x,y,_=proposal
    left=int(round(np.clip(x-40,0,640-80)/scale));top=int(round(np.clip(y-30,0,h*scale-60)/scale))
    right=min(w,int(round(left+80/scale)));bottom=min(h,int(round(top+60/scale)))
    transformed=[]
    for cx,cy,bw,bh in boxes:
        lo=np.maximum([cx-bw/2,cy-bh/2],[left,top]);hi=np.minimum([cx+bw/2,cy+bh/2],[right,bottom]);extent=np.maximum(0,hi-lo)
        fraction=float(np.prod(extent)/max(1e-12,bw*bh))
        if 0<fraction<.98:return None # visible partial target: don't silently label background
        if fraction>=.98:
            transformed.append([float((lo[0]+hi[0])/2-left),float((lo[1]+hi[1])/2-top),float(extent[0]),float(extent[1])])
    transformed.sort(key=lambda b:b[2]*b[3],reverse=True)
    return (left,top,right,bottom),transformed
