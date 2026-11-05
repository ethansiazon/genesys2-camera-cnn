import cv2, numpy as np
W,H=256,192

def sized(image,boxes,width=W,height=H):
    h,w=image.shape[:2];scale=min(width/w,height/h);nw,nh=round(w*scale),round(h*scale);px,py=(width-nw)//2,(height-nh)//2
    out=np.full((height,width,3),114,np.uint8);out[py:py+nh,px:px+nw]=cv2.resize(image,(nw,nh),interpolation=cv2.INTER_AREA if scale<1 else cv2.INTER_LINEAR)
    transformed=boxes*np.array([nw/w,nh/h,nw/w,nh/h],np.float32)+np.array([px,py,0,0],np.float32)
    return out,transformed,(nw/w,nh/h,px,py)
