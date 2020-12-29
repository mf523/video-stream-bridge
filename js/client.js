// https://stackoverflow.com/questions/17530197/how-to-do-network-tracking-or-debugging-webrtc-peer-to-peer-connection

// get DOM elements
var dataChannelLog = document.getElementById('data-channel'),
    iceConnectionLog = document.getElementById('ice-connection-state'),
    iceGatheringLog = document.getElementById('ice-gathering-state'),
    signalingLog = document.getElementById('signaling-state');

const video_local = document.getElementById('video-local');
const video_peer = document.getElementById('video-peer');

let video_stream;

// peer connection
let pc = null;

// data channel
let dc = null, dcInterval = null;

// https://webrtc.github.io/samples/src/content/capture/video-pc/
function maybeCreateStream() {
    console.log('maybeCreateStream() executing...');
    if (video_stream) {
        return;
    }
    if (video_local.captureStream) {
        video_stream = video_local.captureStream();
        console.log('Captured stream from video_local with captureStream',
            video_stream);
        connect();
    } else if (video_local.mozCaptureStream) {
        video_stream = video_local.mozCaptureStream();
        console.log('Captured stream from video_local with mozCaptureStream()',
            video_stream);
        connect();
    } else {
        console.log('captureStream() not supported');
    }
}

// Video tag capture must be set up after video tracks are enumerated.
video_local.oncanplay = maybeCreateStream;
if (video_local.readyState >= 3) { // HAVE_FUTURE_DATA
    // Video is already ready to play, call maybeCreateStream in case oncanplay
    // fired before we registered the event handler.
    maybeCreateStream();
}

function createPeerConnection() {
    console.log(`createPeerConnection`);
    var config = {
        sdpSemantics: 'unified-plan'
    };

    if (document.getElementById('use-stun').checked) {
        config.iceServers = [
            {
                urls: [
                    'stun:stun.l.google.com:19302',
                    'stun:stun1.l.google.com:19302',
                    'stun:stun2.l.google.com:19302',
                    'stun:stun3.l.google.com:19302',
                    'stun:stun4.l.google.com:19302',
                ]
                
            }
        ];
        
        // let server = document.getElementById('stun-url').value
        // config.iceServers = [{urls: [server]}]
    }

    pc = new RTCPeerConnection(config);

    // register some listeners to help debugging
    pc.addEventListener('icegatheringstatechange', function () {
        iceGatheringLog.textContent += ' -> ' + pc.iceGatheringState;
    }, false);
    iceGatheringLog.textContent = pc.iceGatheringState;

    pc.addEventListener('iceconnectionstatechange', function () {
        iceConnectionLog.textContent += ' -> ' + pc.iceConnectionState;
    }, false);
    iceConnectionLog.textContent = pc.iceConnectionState;

    pc.addEventListener('signalingstatechange', function () {
        signalingLog.textContent += ' -> ' + pc.signalingState;
    }, false);
    signalingLog.textContent = pc.signalingState;

    // connect audio / video / stream
    pc.addEventListener('track', function (evt) {
        console.log(`evt.track.kind: ${evt.track.kind}`);
        if (evt.track.kind == 'video')
            document.getElementById('video-peer').srcObject = evt.streams[0];
        else
            document.getElementById('audio').srcObject = evt.streams[0];
    });

    return pc;
}

function negotiate() {
    return pc.createOffer().then(function (offer) {
        return pc.setLocalDescription(offer);
    }).then(function () {
        // wait for ICE gathering to complete
        return new Promise(function (resolve) {
            if (pc.iceGatheringState === 'complete') {
                resolve();
            } else {
                function checkState() {
                    console.log(`iceGatheringState: ${pc.iceGatheringState}`);
                    if (pc.iceGatheringState === 'complete') {
                        pc.removeEventListener('icegatheringstatechange', checkState);
                        resolve();
                    }
                }

                pc.addEventListener('icegatheringstatechange', checkState);
            }
        });
    }).then(function () {
        var offer = pc.localDescription;
        var codec;

        codec = document.getElementById('audio-codec').value;
        if (codec !== 'default') {
            offer.sdp = sdpFilterCodec('audio', codec, offer.sdp);
        }

        codec = document.getElementById('video-codec').value;
        if (codec !== 'default') {
            offer.sdp = sdpFilterCodec('video', codec, offer.sdp);
        }

        document.getElementById('offer-sdp').textContent = offer.sdp;
        return fetch('/offer', {
            body: JSON.stringify({
                sdp: offer.sdp,
                type: offer.type,
                video_transform: document.getElementById('video-transform').value,
                stream_url: document.getElementById('stream-url').value
            }),
            headers: {
                'Content-Type': 'application/json'
            },
            method: 'POST'
        });
    }).then(function (response) {
        return response.json();
    }).then(function (answer) {
        document.getElementById('answer-sdp').textContent = answer.sdp;
        return pc.setRemoteDescription(answer);
    }).catch(function (e) {
        alert(e);
    });
}


function start() {
    document.getElementById('start').style.display = 'none';

    var stream_type = document.getElementById('stream-type').value
    let video = document.getElementById('video-local');
    var stream_url = document.getElementById('stream-url').value

    if (document.getElementById('use-stream').checked) {
        if (stream_type == 'MJPEG') {
            //Leave your .mjpeg video URL here.
            var player = new MJPEG.Player("mjpeg-player", "video-local", stream_url);
            player.start();
        } else if (stream_type == 'HLS') {
            if (Hls.isSupported()) {
                var hls = new Hls({
                    debug: false
                });
                // hls.loadSource('https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8');
                hls.loadSource(stream_url);
                hls.attachMedia(video);
                hls.on(Hls.Events.MEDIA_ATTACHED, function () {
                    video.muted = true;
                    video.play();
                });
            }
                // hls.js is not supported on platforms that do not have Media Source Extensions (MSE) enabled.
                // When the browser has built-in HLS support (check using `canPlayType`), we can provide an HLS manifest (i.e. .m3u8 URL) directly to the video element throught the `src` property.
            // This is using the built-in support of the plain video element, without using hls.js.
            else if (video.canPlayType('application/vnd.apple.mpegurl')) {
                video.src = stream_url;
                video.addEventListener('canplay', function () {
                    video.play();
                });
            }
        }
    } else {
        var constraints = {
            audio: document.getElementById('use-audio').checked,
            video: true
        };
        navigator.mediaDevices.getUserMedia(constraints).then(function (stream) {
            window.stream = stream; // make variable available to browser console
            video_local.srcObject = stream;
        }, function (err) {
            alert('Could not acquire media: ' + err);
        });
    }

    document.getElementById('stop').style.display = 'inline-block';
}


function connect() {
    pc = createPeerConnection();
    console.log(`hha`);

    var time_start = null;

    function current_stamp() {
        if (time_start === null) {
            time_start = new Date().getTime();
            return 0;
        } else {
            return new Date().getTime() - time_start;
        }
    }

    if (document.getElementById('use-datachannel').checked) {
        console.log(`use-datachannel`);
        var parameters = JSON.parse(document.getElementById('datachannel-parameters').value);
        console.log(`use-datachannel 1`);

        dc = pc.createDataChannel('chat', parameters);
        console.log(`use-datachannel 2`);
        dc.onclose = function () {
            clearInterval(dcInterval);
            dataChannelLog.textContent += '- close\n';
        };
        dc.onopen = function () {
            console.log(`onopen`);
            dataChannelLog.textContent += '- open\n';
            dcInterval = setInterval(function () {
                var message = 'ping ' + current_stamp();
                console.log(`ping`);
                dataChannelLog.textContent += '> ' + message + '\n';
                dc.send(message);
            }, 1000);
        };
        dc.onmessage = function (evt) {
            dataChannelLog.textContent += '< ' + evt.data + '\n';

            if (evt.data.substring(0, 4) === 'pong') {
                var elapsed_ms = current_stamp() - parseInt(evt.data.substring(5), 10);
                dataChannelLog.textContent += ' RTT ' + elapsed_ms + ' ms\n';
            }
        };
    }

    var constraints = {
        audio: document.getElementById('use-audio').checked,
        video: true
    };

    var resolution = document.getElementById('video-resolution').value;
    if (resolution) {
        resolution = resolution.split('x');
        constraints.video = {
            width: parseInt(resolution[0], 0),
            height: parseInt(resolution[1], 0)
        };
    }

    if (constraints.audio || constraints.video) {
        if (constraints.video) {
            document.getElementById('media').style.display = 'block';
        }

        if (document.getElementById('use-stream').checked) {
            const video_tracks = video_stream.getVideoTracks();
            console.log(`video tracks count: ${video_tracks.length}`);
            video_stream.getTracks().forEach(function (track) {
                pc.addTrack(track, video_stream);
                console.log('Added local stream to pc');
            });
            negotiate();
        } else {
            const video_tracks = video_stream.getVideoTracks();
            console.log(`video tracks count: ${video_tracks.length}`);
            // const video_tracks = stream.getVideoTracks();
            // console.log(`Using video device: ${video_tracks[0].label}`);
            // window.stream = stream; // make variable available to browser console
            // video_local.srcObject = stream;
            video_stream.getTracks().forEach(function (track) {
                pc.addTrack(track, video_stream);
            });
            negotiate();
        }

    } else {
        negotiate();
    }
}

function stop() {
    document.getElementById('stop').style.display = 'none';
    document.getElementById('start').style.display = 'inline-block';

    // close data channel
    if (dc) {
        dc.close();
    }

    // close transceivers
    if (pc.getTransceivers) {
        pc.getTransceivers().forEach(function (transceiver) {
            if (transceiver.stop) {
                transceiver.stop();
            }
        });
    }

    // close local audio / video
    pc.getSenders().forEach(function (sender) {
        sender.track.stop();
    });

    // close peer connection
    setTimeout(function () {
        pc.close();
    }, 500);
}

function sdpFilterCodec(kind, codec, realSdp) {
    var allowed = []
    var rtxRegex = new RegExp('a=fmtp:(\\d+) apt=(\\d+)\r$');
    var codecRegex = new RegExp('a=rtpmap:([0-9]+) ' + escapeRegExp(codec))
    var videoRegex = new RegExp('(m=' + kind + ' .*?)( ([0-9]+))*\\s*$')

    var lines = realSdp.split('\n');

    var isKind = false;
    for (var i = 0; i < lines.length; i++) {
        if (lines[i].startsWith('m=' + kind + ' ')) {
            isKind = true;
        } else if (lines[i].startsWith('m=')) {
            isKind = false;
        }

        if (isKind) {
            var match = lines[i].match(codecRegex);
            if (match) {
                allowed.push(parseInt(match[1]));
            }

            match = lines[i].match(rtxRegex);
            if (match && allowed.includes(parseInt(match[2]))) {
                allowed.push(parseInt(match[1]));
            }
        }
    }

    var skipRegex = 'a=(fmtp|rtcp-fb|rtpmap):([0-9]+)';
    var sdp = '';

    isKind = false;
    for (var i = 0; i < lines.length; i++) {
        if (lines[i].startsWith('m=' + kind + ' ')) {
            isKind = true;
        } else if (lines[i].startsWith('m=')) {
            isKind = false;
        }

        if (isKind) {
            var skipMatch = lines[i].match(skipRegex);
            if (skipMatch && !allowed.includes(parseInt(skipMatch[2]))) {
                continue;
            } else if (lines[i].match(videoRegex)) {
                sdp += lines[i].replace(videoRegex, '$1 ' + allowed.join(' ')) + '\n';
            } else {
                sdp += lines[i] + '\n';
            }
        } else {
            sdp += lines[i] + '\n';
        }
    }

    return sdp;
}

function escapeRegExp(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); // $& means the whole matched string
}


const canvas_snapshot = window.canvas = document.querySelector('canvas');
canvas_snapshot.width = 480;
canvas_snapshot.height = 360;

const button = document.getElementById('take-snapshot');
button.onclick = function () {
    canvas_snapshot.width = video_peer.videoWidth;
    canvas_snapshot.height = video_peer.videoHeight;
    canvas_snapshot.getContext('2d').drawImage(video_peer, 0, 0, canvas_snapshot.width, canvas_snapshot.height);
};

