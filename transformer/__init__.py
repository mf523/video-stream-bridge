from transformer import common
from transformer import dummy
from transformer import opencv
from transformer import my_nn

import importlib

def get_transformer(video_transform):
    
    importlib.reload(opencv)
    importlib.reload(my_nn)
    importlib.reload(dummy)
    
    video_transform = video_transform.split('.')
    return {
        'opencv': (common.MPVideoTransformTrack, opencv.Worker),
        'my_nn': (common.MPVideoTransformTrack, my_nn.Worker),
    }.get(
        video_transform[0],
        (common.MPVideoTransformTrack, dummy.Worker),
    )
