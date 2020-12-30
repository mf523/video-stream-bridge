import multiprocessing as mp

from transformer import common
from transformer import dummy
from transformer import opencv
from transformer import my_nn

import logging

import importlib

def get_transformer(video_transform):
    
    importlib.reload(opencv)
    importlib.reload(my_nn)
    importlib.reload(dummy)
    importlib.reload(common)
    
    video_transform = video_transform.split('.')
    return {
        'opencv': opencv.Worker,
        'my_nn': my_nn.Worker,
    }.get(
        video_transform[0],
        dummy.Worker,
    )

