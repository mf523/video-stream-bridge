import cv2
from av import VideoFrame

import threading
import multiprocessing as mp
from multiprocessing import shared_memory as shm

import numpy as np
import time
import logging

from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaBlackhole, MediaPlayer, MediaRecorder


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


def processor_on_shm(
        transform_method,
        shape,
        dtype,
        shm_name_source,
        shm_name_target,
        frame_lock,
        args=[],
    ):

    # shm_frame_source = shm.SharedMemory(name=shm_name_source)
    # shm_frame_target = shm.SharedMemory(name=shm_name_target)

    # nd_current_image = frame.to_ndarray(format="bgr24")

    # source = np.ndarray(
    #     nd_current_image.shape,
    #     dtype=nd_current_image.dtype,
    #     buffer=shm_frame_source.buf,
    # )

    # target = np.ndarray(
    #     shape,
    #     dtype=dtype,
    #     buffer=shm_frame_target.buf,
    # )

    frame_lock.acquire()
    source = get_from_shm(shm_name_source, shape=shape)
    frame_lock.release()

    frame_source = VideoFrame.from_ndarray(source, format="bgr24")

    target = transform_method(frame_source, *args)

    frame_lock.acquire()
    put_to_shm(target, shm_name_target)
    frame_lock.release()


class DummyTransformTrack(MediaStreamTrack):
    """
    A video stream track that transforms frames from an another track.
    """

    kind = "video"

    def __init__(self, track, cls_worker, *, params):
        super().__init__()  # don't forget this!
        self.track = track

    async def recv(self):

        frame = await self.track.recv()

        return frame


class MPVideoTransformTrack(MediaStreamTrack):
    """
    A video stream track that transforms frames from an another track.
    """

    kind = "video"
    worker = None
    q_4_worker = mp.JoinableQueue()
    q_4_leader = mp.Queue()
    frame_lock = mp.Lock()

    def __init__(self, cls_worker, track, shm_size, *, params):
        super().__init__()  # don't forget this!
        self.track = track
        self.transform = params['video_transform']
        self.shm_current_frame = shm.SharedMemory(create=True, size=1024 * 1024 * shm_size)
        self.shm_transformed_frame = shm.SharedMemory(create=True, size=1024 * 1024 * shm_size)

    @classmethod
    def create_worker(cls, cls_worker):
        # p = mp.Process(target=cls.worker, args=())
        cls.worker = cls_worker(cls.q_4_worker, cls.q_4_leader, args=(cls.frame_lock, ))
        cls.worker.start()

    async def recv(self):
        frame = await self.track.recv()

        self.frame_lock.acquire()
        put_to_shm(frame, self.shm_current_frame.name)
        self.frame_lock.release()

        current_frame = frame.to_ndarray(format="bgr24")

        if self.transform in self.worker.transform_list:
            self.q_4_worker.put(
                {
                    "shape": current_frame.shape,
                    "dtype": current_frame.dtype,
                    "video_transform": self.transform,
                    "shm_name_current_frame": self.shm_current_frame.name,
                    "shm_name_transformed_frame": self.shm_transformed_frame.name,
                }
                
            )
            result = self.q_4_leader.get()
            # logging.info(f"result: {result}")
            

            self.frame_lock.acquire()
            transformed_image = get_from_shm(self.shm_transformed_frame.name, shape=current_frame.shape)
            self.frame_lock.release()

            new_frame = VideoFrame.from_ndarray(transformed_image, format="bgr24")
            new_frame.pts = frame.pts
            new_frame.time_base = frame.time_base

            return new_frame

        else:
            return frame


