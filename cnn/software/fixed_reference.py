import torch

class Fixed(torch.fx.Interpreter):
    def __init__(self,model):super().__init__(model);self.clipped=0
    def run_node(self,node):
        y=super().run_node(node)
        if isinstance(y,torch.Tensor):
            self.clipped+=int(((y < -512)|(y >8388607/16384)).sum());return torch.round(y*16384).clamp(-8388608,8388607)/16384
        return y
