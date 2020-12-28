from aiortc import MediaStreamTrack


class DummyTransformTrack(MediaStreamTrack):
    """
    A video stream track that transforms frames from an another track.
    """

    kind = "video"

    def __init__(self, track, *, params):
        super().__init__()  # don't forget this!
        self.track = track

    async def recv(self):

        frame = await self.track.recv()

        return frame
