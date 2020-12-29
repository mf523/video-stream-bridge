from aiortc import MediaStreamTrack

import multiprocessing as mp
from multiprocessing import shared_memory as shm
import signal

from .common import (
    put_to_shm,
    get_from_shm,
    processor_on_shm,
)


def dummy_transform(frame):

    return frame


class Transformer(mp.Process):
    
    transform_list = {
        "none": None,
    }

    def __init__(
            self,
            q_task,
            q_result,
            frame_lock,
            shm_name_current_frame,
            shm_name_transformed_frame,
            *,
            args=[]
    ):
        # https://noswap.com/blog/python-multiprocessing-keyboardinterrupt
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        mp.Process.__init__(self, args=args)
        self.q_task = q_task
        self.q_result = q_result
        self.frame_lock = frame_lock
        self.shm_name_current_frame = shm_name_current_frame
        self.shm_name_transformed_frame = shm_name_transformed_frame

    def run(self):
        proc_name = self.name
        while True:
            msg = None
            try:
                msg = self.q_task.get(False)
            except Exception:
                # logging.info(f"result: Empty")
                import time
                time.sleep(1)
                None
            if msg is None:
                # Poison pill means shutdown
                # print '%s: Exiting' % proc_name

                break
            else:
                # self.q_task.task_done()
                transform_method = self.transform_list.get(msg.get("video_transform"))

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
                # self.q_4_worker.task_done()
                self.q_result.put(answer)
            
        return

