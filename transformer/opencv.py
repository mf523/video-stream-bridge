from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaBlackhole, MediaPlayer, MediaRecorder

import cv2
from av import VideoFrame

import threading
import multiprocessing as mp
from multiprocessing import shared_memory as shm
import signal

import numpy as np
import time

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

frame_sema = threading.BoundedSemaphore(value=1)


def opencv_cartoon(frame):
    nd_current_image = frame.to_ndarray(format="bgr24")

    # prepare color
    img_color = cv2.pyrDown(cv2.pyrDown(nd_current_image))
    for _ in range(6):
        img_color = cv2.bilateralFilter(img_color, 9, 9, 7)
    img_color = cv2.pyrUp(cv2.pyrUp(img_color))

    # prepare edges
    img_edges = cv2.cvtColor(nd_current_image, cv2.COLOR_RGB2GRAY)
    img_edges = cv2.adaptiveThreshold(
        cv2.medianBlur(img_edges, 7),
        255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY,
        9,
        2,
    )
    img_edges = cv2.cvtColor(img_edges, cv2.COLOR_GRAY2RGB)

    # combine color and edges
    img = cv2.bitwise_and(img_color, img_edges)

    frame_new = VideoFrame.from_ndarray(img, format="bgr24")

    return frame_new


def opencv_edges(frame):
    nd_current_image = frame.to_ndarray(format="bgr24")

    img = cv2.cvtColor(cv2.Canny(nd_current_image, 100, 200), cv2.COLOR_GRAY2BGR)

    frame_new = VideoFrame.from_ndarray(img, format="bgr24")

    return frame_new


def opencv_rotate(frame):
    nd_current_image = frame.to_ndarray(format="bgr24")

    ts = time.gmtime()
    rows, cols, _ = nd_current_image.shape
    M = cv2.getRotationMatrix2D((cols / 2, rows / 2), ts.tm_sec * 12, 1)
    img = cv2.warpAffine(nd_current_image, M, (cols, rows))

    frame_new = VideoFrame.from_ndarray(img, format="bgr24")

    return frame_new


# if __name__ == '__main__':
#     with Manager() as manager:
#         d = manager.dict()
#         l = manager.list(range(10))
#
#         p = Process(target=f, args=(d, l))
#         p.start()
#         p.join()
#
#         print(d)
#         print(l)


class Worker(mp.Process):
    transform_list = {
        "opencv.cartoon": opencv_cartoon,
        "opencv.edges": opencv_edges,
        "opencv.rotate": opencv_rotate,
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
                import time
                # Poison pill means shutdown
                # print '%s: Exiting' % proc_name

                # break
                logger.info(f"{self.pid} got empty msg, sleeping")
                time.sleep(1)
            else:
                # self.q_task.task_done()
                transform_method = self.transform_list.get(msg.get("video_transform"))
                logger.info(f"{self.pid} transform_method: {transform_method}")

                processor_on_shm(
                    transform_method,
                    shape=msg.get("shape"),
                    dtype=msg.get("dtype"),
                    shm_name_source=self.shm_name_current_frame,
                    shm_name_target=self.shm_name_transformed_frame,
                    frame_lock=self.frame_lock,
                )

                # print '%s: %s' % (proc_name, next_task)
                answer = f"{transform_method} done!"

        return


