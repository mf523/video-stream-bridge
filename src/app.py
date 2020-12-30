import os
import signal
import psutil
import argparse

import time

from datetime import datetime

import asyncio
import json
import logging
import ssl
import uuid

from aiohttp import web

from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaBlackhole, MediaPlayer, MediaRecorder

from backend import get_transformer
from backend import track as bt

import multiprocessing as mp

SRC_ROOT = os.path.dirname(__file__)
PROJECT_ROOT = os.path.dirname(SRC_ROOT)

logger = logging.getLogger("pc")
pcs = set()

worker_list = {
    ':parent:': os.getpid(),
}


def create_worker(video_transform, video_stream):
    global worker_list

    logger.info(f"video_transform: {video_transform}")

    if video_transform in worker_list:
        worker = worker_list.get(video_transform)
    else:
        cls_worker = get_transformer(video_transform)
        worker = cls_worker(
            video_stream,
        )

        worker.start()

        video_stream.transformer_pid = worker.pid
        logger.info(f"pid: {worker.pid} shm source:{video_stream.shm_current_frame.name} target:{video_stream.shm_transformed_frame.name}")

        worker_list['video_transform'] = worker

    logger.info(f"created worker: {worker}")

    return worker


async def index(request):
    logging.info(f"request: '{request}'")
    content = open(os.path.join(SRC_ROOT, "index.html"), "r").read()
    return web.Response(content_type="text/html", text=content)


async def js(request):
    # https://docs.aiohttp.org/en/stable/web_quickstart.html#aiohttp-web-variable-handler
    content = open(os.path.join(SRC_ROOT, f"js/{request.match_info['filename']}"), "r").read()
    return web.Response(content_type="application/javascript", text=content)


async def img(request):
    # https://docs.aiohttp.org/en/stable/web_quickstart.html#aiohttp-web-variable-handler
    content = open(os.path.join(PROJECT_ROOT, f"img/{request.match_info['filename']}"), "rb").read()
    return web.Response(content_type="application/octet-stream", body=content)

async def offer(request):
    logging.info(f"request: '{request}'")
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pc_id = f"PeerConnection({uuid.uuid4()})"
    pcs.add(pc)

    def log_info(msg, *args):
        logger.info(pc_id + " " + msg, *args)

    log_info("Created for %s", request.remote)

    # prepare local media
    if args.write_audio:
        recorder = MediaRecorder(args.write_audio)
    else:
        recorder = MediaBlackhole()

    @pc.on("datachannel")
    def on_datachannel(channel):
        @channel.on("message")
        def on_message(message):
            if isinstance(message, str) and message.startswith("ping"):
                channel.send("pong" + message[4:])

    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        log_info("ICE connection state is %s", pc.iceConnectionState)
        if pc.iceConnectionState == "failed":
            await pc.close()
            pcs.discard(pc)

    on_track_task = None
    @pc.on("track")
    def on_track(track):
        log_info("Track %s received", track.kind)
        log_info(f"Track: {track}, pc: {pc}")

        if track.kind == "audio":
            # pc.addTrack(player.audio)
            # recorder.addTrack(track)
            None

        elif track.kind == "video":

            cls_worker = get_transformer(params["video_transform"])
            log_info(f"track.kind: {track.kind}, video_transform: {params['video_transform']}, cls_worker: {cls_worker}")

            cls_video_track = bt.VideoTransformTrack
            video_stream = cls_video_track(
                track,
                mp.Lock(),
                params=params,
            )
            pc.addTrack(video_stream)

            # wm = transformer.WorkerManager()
            # worker_list.append()
            # cls_wm.create_worker()

            worker = create_worker(params['video_transform'], video_stream)
            video_stream.p_in = worker.p_in

        @track.on("ended")
        async def on_ended():
            log_info("Track %s ended", track.kind)
            await recorder.stop()


    # handle offer
    await pc.setRemoteDescription(offer)
    await recorder.start()

    # send answer
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.Response(
        content_type="application/json",
        text=json.dumps(
            {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
        ),
    )


async def on_shutdown(app):
    # close peer connections
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()


def kill_child_processes(parent_pid, sig=signal.SIGTERM):
    try:
        parent = psutil.Process(parent_pid)
    except psutil.NoSuchProcess:
        return
    children = parent.children(recursive=True)
    for process in children:
        process.send_signal(sig)


if __name__ == "__main__":
    mp.set_start_method('spawn', force=True)

    format = "%(asctime)s: %(message)s"
    logging.basicConfig(format=format, level=logging.INFO,
                        datefmt="%H:%M:%S")

    parser = argparse.ArgumentParser(
        description="WebRTC audio / video / data-channels demo"
    )
    # http://d2qohgpffhaffh.cloudfront.net/HLS/vanlife/withad/sdr_uncage_vanlife_admarker_60sec.m3u8
    # http://192.168.1..104:8080/video
    parser.add_argument('--width', default=320)
    parser.add_argument('--model_path', default='./pretrained_model')
    parser.add_argument('--style', default='Hayao')
    parser.add_argument('--output-dir', default=None)
    parser.add_argument('--cuda', type=int, default=0)
    parser.add_argument("--cert-file", help="SSL certificate file (for HTTPS)")
    parser.add_argument("--key-file", help="SSL key file (for HTTPS)")
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host for HTTP server (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=8080, help="Port for HTTP server (default: 8080)"
    )
    parser.add_argument("--verbose", "-v", action="count")
    parser.add_argument("--write-audio", help="Write received audio to a file")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    flip_horizon = False

    if args.cert_file:
        ssl_context = ssl.SSLContext()
        # ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(args.cert_file, args.key_file)
    else:
        ssl_context = None

    try:
        
        app = web.Application()
        app.on_shutdown.append(on_shutdown)
        app.router.add_get("/", index)
        app.router.add_get("/js/{filename}", js)
        app.router.add_get("/img/{filename}", img)
        app.router.add_post("/offer", offer)
        web.run_app(
            app, access_log=None, host=args.host, port=args.port, ssl_context=ssl_context
        )

    except KeyboardInterrupt:
        print("Caught KeyboardInterrupt, terminating workers")
        # pool.terminate()
        # pool.join()
        pid = os.getpid()
        kill_child_processes(pid)

        for item in worker_list.items():
            logger.info(f"killing process '{item[0]}'")
            if isinstance(item[1], "Process"):
                print("kill it...")

    else:
        None

    finally:
        # https://stackoverflow.com/questions/3332043/obtaining-pid-of-child-process

        pid = os.getpid()
        kill_child_processes(pid)

