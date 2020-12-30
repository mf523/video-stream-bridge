from aiortc import MediaStreamTrack

import multiprocessing as mp
from multiprocessing import shared_memory as shm
import signal

from .common import (
    put_to_shm,
    get_from_shm,
    processor_on_shm,
)


import logging
# import auxiliary_module

# create logger with 'spam_application'
logger = logging.getLogger('server')
logger.setLevel(logging.DEBUG)
# create file handler which logs even debug messages
fh = logging.FileHandler('server.log')
fh.setLevel(logging.DEBUG)
logger.addHandler(fh)


def dummy_transform(frame):

    return frame


class Worker(mp.Process):
    
    transform_list = {
        "none": None,
    }

    def __init__(
            self,
            frame_lock,
            shm_name_current_frame,
            shm_name_transformed_frame,
            *,
            args=[]
    ):
        mp.Process.__init__(self, args=args)
        self.daemon = True
        self.p_out, self.p_in = mp.Pipe(False) # not duplex
        self.frame_lock = frame_lock
        self.shm_name_current_frame = shm_name_current_frame
        self.shm_name_transformed_frame = shm_name_transformed_frame

    def run(self):
        # https://noswap.com/blog/python-multiprocessing-keyboardinterrupt
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        proc_name = self.name
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
                transform_method = self.transform_list.get(msg.get("video_transform"))
                logger.info(f"{self.pid} transform_method: {transform_method}")

                processor_on_shm(
                    dummy_transform,
                    shape=msg.get("shape"),
                    dtype=msg.get("dtype"),
                    shm_name_source=self.shm_name_current_frame,
                    shm_name_target=self.shm_name_transformed_frame,
                    frame_lock=self.frame_lock,
                )
                
                # print '%s: %s' % (proc_name, next_task)
                answer = f"{transform_method} done!"
            
        return

