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

from . import (
    get_from_shm,
    BaseWorker,
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


class Worker(BaseWorker):
    
    transform_list = {
        "opencv.cartoon": opencv_cartoon,
        "opencv.edges": opencv_edges,
        "opencv.rotate": opencv_rotate,
    }
        
    def transform(self, frame, transform_method=None, *, args={}):

        return transform_method(frame)



