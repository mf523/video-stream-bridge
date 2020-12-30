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


class WorkerManager(mp.Process):

    def __init__(self, q_4_worker, q_4_leader, shm_name_current_frame, shm_name_transformed_frame, frame_lock):
        # super().__init__()  # don't forget this!
        super(WorkerManager, self).__init__()
        self.q_4_worker = q_4_worker
        self.q_4_leader = q_4_leader
        self.shm_name_current_frame = shm_name_current_frame
        self.shm_name_transformed_frame = shm_name_transformed_frame
        self.frame_lock = frame_lock
        self.transformer = None

    @classmethod
    def create_worker(cls, cls_worker):
        p = cls_worker(cls.shm_current_frame.name, cls.shm_transformed_frame.name, cls.frame_lock)
        p.start()

    def run(self):
        while True:
            msg = self.q_4_worker.get()
            if msg is None:
                import time
                # Poison pill means shutdown
                # print '%s: Exiting' % proc_name

                # break
                logging(f"got empty msg, sleeping")
                time.sleep(1)
            else:
                # self.q_4_worker.task_done()

                video_transform = msg.get("video_transform")

                if self.transformer is None:
                    cls_transformer = get_transformer(video_transform)
                    transform_method = self.transform_list.get(video_transform)

        cls.worker = cls_worker(cls.q_4_worker, cls.q_4_leader, args=(None,))

        return frame
