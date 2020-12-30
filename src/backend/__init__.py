from av import VideoFrame
import numpy as np
from av import VideoFrame

import multiprocessing as mp
from multiprocessing import shared_memory as shm

import signal
import time

import signal

import importlib

import logging
# import auxiliary_module

# create logger with 'spam_application'
logger = logging.getLogger('backend')
logger.setLevel(logging.DEBUG)
# create file handler which logs even debug messages
fh = logging.FileHandler('backend.log')
fh.setLevel(logging.DEBUG)
logger.addHandler(fh)


def st_time(func):
    """
        st decorator to calculate the total time of a func
    """

    def st_func(*args, **keyArgs):
        t1 = time.time()
        r = func(*args, **keyArgs)
        t2 = time.time()
        print(f"Function={func.__name__}, Time={t2 - t1}")
        return r

    return st_func
    

def put_to_shm(frame, shm_name):

    shm_frame = shm.SharedMemory(name=shm_name)

    nd_current_image = frame.to_ndarray(format="bgr24")

    target = np.ndarray(
        nd_current_image.shape,
        dtype=nd_current_image.dtype,
        buffer=shm_frame.buf,
    )

    target[:] = nd_current_image[:]


def get_from_shm(shm_name, *, shape, dtype='uint8'):

    shm_frame = shm.SharedMemory(name=shm_name)

    nd_new_image = np.ndarray(
        shape,
        dtype=dtype,
    )

    source = np.ndarray(
        shape,
        dtype=dtype,
        buffer=shm_frame.buf,
    )

    nd_new_image[:] = source[:]

    return nd_new_image


def get_transformer(video_transform):
    
    video_transform = video_transform.split('.')
    
    if video_transform[0] == 'none':
        model_name = 'dummy'
    else:
        model_name = video_transform[0]
    
    transformer = importlib.import_module(f"backend.{model_name}")
    cls_worker = getattr(transformer, "Worker")

    return cls_worker


class BaseWorker(mp.Process):
    
    transform_list = {
        "none": None,
    }

    def __init__(
            self,
            video_track,
            *,
            args={},
    ):
        mp.Process.__init__(self, args=args)
        self.daemon = True
        self.p_out, self.p_in = mp.Pipe(False) # not duplex
        self.frame_lock = video_track.frame_lock
        logger.info(f"video_stream lock {self.frame_lock}")
        self.shm_name_current_frame = video_track.shm_current_frame.name
        self.shm_name_transformed_frame = video_track.shm_transformed_frame.name

    def run(self):
        # https://noswap.com/blog/python-multiprocessing-keyboardinterrupt
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        logger.info(f"video_stream lock 2 ")
        logger.info(f"{self.pid} - pipe polling")
        while True:
            msg = None
            if self.p_out.poll():
                logger.info(f"{self.pid} - pipe read start")
                msg = self.p_out.recv()
                logger.info(f"{self.pid} - pipe read stop")
            else:
                # logging.info(f"result: Empty")
                import time
                time.sleep(1)
                None
            if msg is None:
                # Poison pill means shutdown
                # print '%s: Exiting' % proc_name

                logger.info(f"{self.pid} got empty msg, sleeping")  

                time.sleep(1)
            else:
                # self.q_task.task_done()

                transform_method = self.transform_list.get(msg.get("video_transform"), None)
                logger.info(f"{self.pid} before _transform")  
                self._transform(
                    transform_method,
                    video_transform=msg.get("video_transform"),
                    shape=msg.get("shape"),
                    dtype=msg.get("dtype"),
                )
                logger.info(f"{self.pid} after _transform")  
                
                # print '%s: %s' % (proc_name, next_task)
                answer = f"{transform_method} done!"
            
        return
    

    def _transform(self, transform_method, video_transform, shape, dtype, *, args={}):
        
        if transform_method is None:
            transform_method = dummy.dummy_transform
        
        self.frame_lock.acquire()
        source = get_from_shm(self.shm_name_current_frame, shape=shape, dtype=dtype)
        self.frame_lock.release()
        
        # logger.info(f"{self.pid} transform_method excuted on shm: {self.shm_name_current_frame}")
    
        frame_source = VideoFrame.from_ndarray(source, format="bgr24")
    
        transformed = self.transform(
                frame_source,
                transform_method,
                args={
                    'video_transform': video_transform,
                },
            )
    
        self.frame_lock.acquire()
        put_to_shm(transformed, self.shm_name_transformed_frame)
        self.frame_lock.release()
        

    def transform(self, frame, transform_method=None, *, args={}):
        
        return frame
        
