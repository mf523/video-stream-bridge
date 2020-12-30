from aiortc import MediaStreamTrack

import multiprocessing as mp
from multiprocessing import shared_memory as shm
import signal

from . import (
    get_from_shm,
    BaseWorker,
)


import logging
# import auxiliary_module

# create logger with 'spam_application'
logger = logging.getLogger('backend')
logger.setLevel(logging.DEBUG)
# create file handler which logs even debug messages
fh = logging.FileHandler('backend.log')
fh.setLevel(logging.DEBUG)
logger.addHandler(fh)


def dummy_transform(frame):

    return frame


class Worker(BaseWorker):
    
    transform_list = {
        "none": None,
    }
        
    def transform(self, frame, transform_method=None, *, args={}):
        
        return dummy_transform(frame)
        


