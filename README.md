# video-stream-bridge
A small program that play and send video stream over to another backend service for processing, then play the processed stream in live.

## Requirements
* Python 3.8+
* 

## Throubleshooting
* ```RuntimeError: Cannot re-initialize CUDA in forked subprocess. To use CUDA with multiprocessing, you must use the 'spawn' start method```
** https://discuss.pytorch.org/t/multiprocessing-for-cuda-error/16866/4
** https://github.com/pytorch/pytorch/issues/40403
