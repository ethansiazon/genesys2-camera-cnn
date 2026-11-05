import cv2,numpy as np

class Motion:
    def __init__(self):self.previous=None;self.window=None
    def propose(self,image):
        h,w=image.shape[:2];scale=640/w
        gray=cv2.cvtColor(cv2.resize(image,(640,round(h*scale))),cv2.COLOR_BGR2GRAY).astype(np.float32)
        gray=cv2.GaussianBlur(gray,(3,3),0)
        if self.previous is None:
            self.previous=gray;self.window=cv2.createHanningWindow((gray.shape[1],gray.shape[0]),cv2.CV_32F)
            return [],{'shift':[0.,0.],'phase_response':0.,'warmup':True}
        previous=self.previous;self.previous=gray
        # phaseCorrelate can modify inputs while windowing: explicit copies.
        shift,response=cv2.phaseCorrelate(previous.copy(),gray.copy(),self.window)
        dx,dy=shift
        if not np.isfinite([dx,dy,response]).all() or response<.12 or max(abs(dx),abs(dy))>40:dx=dy=0.
        matrix=np.float32([[1,0,dx],[0,1,dy]])
        aligned=cv2.warpAffine(previous,matrix,(gray.shape[1],gray.shape[0]),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
        valid=cv2.warpAffine(np.ones_like(gray,np.uint8),matrix,(gray.shape[1],gray.shape[0]),flags=cv2.INTER_NEAREST,borderMode=cv2.BORDER_CONSTANT)
        valid=cv2.erode(valid,np.ones((7,7),np.uint8));valid[:4]=0;valid[-4:]=0;valid[:,:4]=0;valid[:,-4:]=0
        residual=np.abs(gray-aligned);values=residual[valid>0]
        med=float(np.median(values));mad=float(np.median(np.abs(values-med)))
        threshold=max(8.,med+6.*1.4826*mad)
        # Summed local change preserves compact targets; suppression limits redundancy.
        residual=np.maximum(0.,residual-threshold)*valid
        score=cv2.boxFilter(residual,-1,(5,5),normalize=False)
        proposals=[]
        for _ in range(4):
            _,maximum,_,point=cv2.minMaxLoc(score)
            if maximum<=0:break
            x,y=point;proposals.append([float(x),float(y),float(maximum)])
            cv2.circle(score,(x,y),32,0.,-1)
        return proposals,{'shift':[float(dx),float(dy)],'phase_response':float(response),'residual_threshold':threshold,'warmup':False}
