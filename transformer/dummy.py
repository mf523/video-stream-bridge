from aiortc import MediaStreamTrack

import multiprocessing as mp
from multiprocessing import shared_memory as shm

from .common import (
    put_to_shm,
    get_from_shm,
    processor_on_shm,
)


def dummy_transform(frame):

    return frame


class Worker(mp.Process):
    
    transform_list = {
        "none": None,
    }

    def __init__(self, q_4_worker, q_4_leader, *, args):
        mp.Process.__init__(self, args=args)
        self.q_4_worker = q_4_worker
        self.q_4_leader = q_4_leader
        self.frame_lock = args[0]

    def run(self):
        proc_name = self.name
        while True:
            msg = self.q_4_worker.get()
            if msg is None:
                # Poison pill means shutdown
                # print '%s: Exiting' % proc_name

                break
            else:
                self.q_4_worker.task_done()
                transform_method = self.transform_list.get(msg.get("video_transform"))

                processor_on_shm(
                    dummy_transform,
                    shape=msg.get("shape"),
                    dtype=msg.get("dtype"),
                    shm_name_source=msg.get("shm_name_current_frame"),
                    shm_name_target=msg.get("shm_name_transformed_frame"),
                    frame_lock=self.frame_lock,
                )
                
                # print '%s: %s' % (proc_name, next_task)
                answer = f"{transform_method} done!"
                # self.q_4_worker.task_done()
                self.q_4_leader.put(answer)
            
        return

