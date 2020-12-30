import os

from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaBlackhole, MediaPlayer, MediaRecorder

import cv2
from av import VideoFrame

import torch
import torchvision.transforms as transforms
from torch.autograd import Variable
# import torchvision.utils as vutils

import threading
import multiprocessing as mp
from multiprocessing import shared_memory as shm
import signal

import numpy as np
import time

import pathlib

from . import (
    get_from_shm,
    st_time,
    BaseWorker,
)

from backend.network.Transformer import Transformer


import logging
# import auxiliary_module

# create logger with 'spam_application'
logger = logging.getLogger('backend')
logger.setLevel(logging.DEBUG)
# create file handler which logs even debug messages
fh = logging.FileHandler('backend.log')
fh.setLevel(logging.DEBUG)
logger.addHandler(fh)

torch.multiprocessing.set_start_method('spawn', force=True)

cartoon_gan_root_dir = pathlib.Path(__file__).parent.absolute().as_posix() + "/../.."
pretrained_model_dir = f"{cartoon_gan_root_dir}/pretrained_model"

inference_sema = threading.BoundedSemaphore(value=1)
inference_lock = mp.Lock()

@st_time
def my_nn_transform(frame, model, cuda):

    nd_current_image = frame.to_ndarray(format="bgr24")
    logging.info(f"nd_current_image shape: {nd_current_image.shape}")

    # with frame_sema:
    # RGB -> BGR
    input_image_bgr = nd_current_image[:, :, [2, 1, 0]]

    input_image_bgr = transforms.ToTensor()(input_image_bgr).unsqueeze(0)
    # preprocess, (-1, 1)
    input_image_bgr = -1 + 2 * input_image_bgr

    frame_new = None
    with torch.no_grad():
        if cuda:
            input_image_bgr = input_image_bgr.cuda()
        else:
            input_image_bgr = input_image_bgr.float()

        with inference_sema:
            try:
                # forward
                # logging.info(f"Thread '{thread_name}': inferencing")
                
                output_image = model(input_image_bgr)
                
                output_image = output_image[0]
                # BGR -> RGB
                output_image = output_image[[2, 1, 0], :, :]
                # deprocess, (0, 1)
                output_image = output_image.data.cpu().float() * 0.5 + 0.5

                im = transforms.ToPILImage()(output_image)

                # with frame_sema:
                transformed_frame = np.array(im)
                # logging.info(f"Thread '{thread_name}': transformed_frame updated")

            finally:
                None

            frame_new = VideoFrame.from_ndarray(transformed_frame, format="bgr24")
            
            logging.info(f"transformed_frame shape: {transformed_frame.shape}")

    return frame_new


class Worker(BaseWorker):
    transform_list = {
        "my_nn.cartoon.Hayao": "Hayao",
        "my_nn.cartoon.Hosoda": "Hosoda",
        "my_nn.cartoon.Paprika": "Paprika",
        "my_nn.cartoon.Shinkai": "Shinkai",
    }

    def __init__(
            self,
            video_track,
            *,
            args={},
    ):
        super().__init__(video_track, args=args)

        self.models = {}

        cuda = False
        try:
            current_device = torch.cuda.current_device()
            torch.cuda.device(0)

            device_count = torch.cuda.device_count()

            device_name = torch.cuda.get_device_name(0)

            cuda = torch.cuda.is_available()
            logging.info(
                f"{self.pid} - current_device: {current_device}, device_count: {device_count}, device_name: {device_name}, cuda: {cuda}")
        except Exception:
            logging.info(f"{self.pid} - cuda not supported")

        self.cuda = cuda


    def transform(self, frame, transform_method=None, *, args={}):
        global pretrained_model_dir
        
        video_transform = args['video_transform']
        
        transform_model_name_prefix = self.transform_list.get(video_transform)
        logger.info(f"{self.pid} - transform_model_name_prefix: {transform_model_name_prefix}")

        if video_transform not in self.models:
            model = Transformer()
            model.load_state_dict(torch.load(
                os.path.join(pretrained_model_dir, transform_model_name_prefix + '_net_G_float.pth')))
            model.eval()

            if self.cuda:
                model.cuda()
            else:
                model.float()

            self.models[video_transform] = model

        else:
            model = self.models[video_transform]
            # logger.info(f"{self.pid} - model found: {transform_model_name_prefix}")
            
        transform_method = my_nn_transform

        return transform_method(frame, model, self.cuda)


