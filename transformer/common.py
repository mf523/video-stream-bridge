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
    source = get_from_shm(shm_name_source, shape=shape, dtype=dtype)
    frame_lock.release()

    frame_source = VideoFrame.from_ndarray(source, format="bgr24")

    transformed = transform_method(frame_source, *args)

    frame_lock.acquire()
    put_to_shm(transformed, shm_name_target)
    frame_lock.release()





class VideoTransformTrack(MediaStreamTrack):
    """
    A video stream track that transforms frames from an another track.
    """

    kind = "video"
    q_task = mp.JoinableQueue()
    q_result = mp.Queue()
    frame_lock = mp.Lock()
    shm_size = 10
    shm_current_frame = shm.SharedMemory(create=True, size=1024 * 1024 * shm_size)
    shm_transformed_frame = shm.SharedMemory(create=True, size=1024 * 1024 * shm_size)

    def __init__(self, track, *, params):
        super().__init__()  # don't forget this!
        self.workers = {}
        self.track = track
        self.transform = params['video_transform']
        self.count = 0

    async def recv(self):
        frame = await self.track.recv()
        self.count += 1

        self.frame_lock.acquire()
        put_to_shm(frame, self.shm_current_frame.name)
        self.frame_lock.release()

        current_frame = frame.to_ndarray(format="bgr24")

        if self.count % 10 == 0:
            self.q_task.put(
                {
                    "shape": current_frame.shape,
                    "dtype": current_frame.dtype,
                    "video_transform": self.transform,
                }
            )
        try:
            result = self.q_result.get(False)
            # logging.info(f"result: {result}")
        except Exception:
            # logging.info(f"result: Empty")
            None

        self.frame_lock.acquire()
        transformed_image = get_from_shm(self.shm_transformed_frame.name, shape=current_frame.shape)
        self.frame_lock.release()

        new_frame = VideoFrame.from_ndarray(transformed_image, format="bgr24")
        new_frame.pts = frame.pts
        new_frame.time_base = frame.time_base

        return new_frame



