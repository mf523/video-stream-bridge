from .dummy import DummyTransformTrack
from .opencv import OpenCVTransformTrack
from .my_nn import MyNNTransformTrack


def get_transformer(video_transform):
    video_transform = video_transform.split('.')
    return {
        'opencv': OpenCVTransformTrack,
        'my_nn': MyNNTransformTrack,
    }.get(
        video_transform[0],
        DummyTransformTrack,
    )
