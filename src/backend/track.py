import cv2
from av import VideoFrame
import numpy as np
import json

from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaBlackhole, MediaPlayer, MediaRecorder

import multiprocessing as mp
from multiprocessing import shared_memory as shm

from . import (
    put_to_shm,
    get_from_shm,
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



class VideoTransformTrack(MediaStreamTrack):
    """
    A video stream track that transforms frames from an another track.
    """

    kind = "video"
    p_in = None
    shm_size = 10
    shm_current_frame = shm.SharedMemory(create=True, size=1024 * 1024 * shm_size)
    shm_transformed_frame = shm.SharedMemory(create=True, size=1024 * 1024 * shm_size)

    def __init__(self, track, frame_lock, *, params):
        super().__init__()  # don't forget this!
        self.workers = {}
        self.track = track
        self.transform = params['video_transform']
        self.count = 0
        self.transformer_pid = None
        self.frame_lock = frame_lock

    async def recv(self):
        frame = await self.track.recv()
        self.count += 1

        self.frame_lock.acquire()
        put_to_shm(frame, self.shm_current_frame.name)
        self.frame_lock.release()

        current_frame = frame.to_ndarray(format="bgr24")
        # logger.info(f"current_frame.shape: {current_frame.shape}")

        if self.count % 10 == 0:
            self.p_in.send(
                {
                    "shape": current_frame.shape,
                    "dtype": current_frame.dtype,
                    "video_transform": self.transform,
                }
            )

        self.frame_lock.acquire()
        transformed_image = get_from_shm(self.shm_transformed_frame.name, shape=current_frame.shape)
        self.frame_lock.release()

        new_frame = VideoFrame.from_ndarray(transformed_image, format="bgr24")
        new_frame.pts = frame.pts
        new_frame.time_base = frame.time_base

        return new_frame



