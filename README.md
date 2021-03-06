# Video Stream Bridge
A small program that play and send video stream over to another backend service for processing, then play the processed stream in live.

## Features
* Media support: MP4, MJPEG, HLS, Webcam, screenshare
* Connectivity: video on internet/local network to processing service on internet/local network
* Backend processing: customizable backend processing, plug and play
* UI Screenshot

![img/screenshot1.jpg](img/screenshot1.jpg)

## Requirements
* Python 3.8+ (required by shm)
* aiortc 1+
* opencv-python 4.4+
* Pillow 8+


## Throubleshooting
* ```RuntimeError: Cannot re-initialize CUDA in forked subprocess. To use CUDA with multiprocessing, you must use the 'spawn' start method```
** https://discuss.pytorch.org/t/multiprocessing-for-cuda-error/16866/4
** https://github.com/pytorch/pytorch/issues/40403
* getUserMedia, getDisplayMedia are not available via http protocol
** https://stackoverflow.com/questions/60957829/navigator-mediadevices-is-undefined
* some mjpeg cams do not support CORS
* webcam and sharescreen requires safe network environment

## References
* https://webrtc.github.io/samples/
* https://github.com/aiortc/aiortc
* https://www.lynnislu.com/posts/mjpeg/
* https://hls-js.netlify.app/demo/
