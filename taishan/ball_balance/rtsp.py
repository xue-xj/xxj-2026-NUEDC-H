"""GStreamer RTSP service consuming the latest raw frame, independent of RKNN."""
import logging
import threading
import time

LOG = logging.getLogger(__name__)


class RtspServer:
    def __init__(self, config, frames, stop):
        import gi
        gi.require_version('Gst', '1.0')
        gi.require_version('GstRtspServer', '1.0')
        from gi.repository import Gst, GstRtspServer, GLib
        Gst.init(None)
        self.Gst, self.GLib = Gst, GLib
        self.config, self.frames, self.stop = config, frames, stop
        self.thread = None
        for plugin in ('appsrc', 'videoconvert', 'queue', 'h264parse', 'rtph264pay', config['encoder']):
            if Gst.ElementFactory.find(plugin) is None:
                raise RuntimeError(f'Missing GStreamer plugin: {plugin}; see docs/deployment.md')
        # Rockchip plugin properties vary by image. Do not guess vendor bitrate units.
        if config['encoder'] == 'x264enc':
            encoder = (f'x264enc tune=zerolatency speed-preset=ultrafast '
                       f'bitrate={config["bitrate_kbps"]} key-int-max={config["fps"]}')
        else:
            encoder = 'mpph264enc'
            LOG.warning('MPP encoder selected: bitrate_kbps is only configured for x264enc; tune vendor properties on board')
        size = config['width'] * config['height'] * 3
        launch = (f'( appsrc name=source is-live=true block=false format=time max-bytes={size * 2} '
                  f'! queue max-size-buffers=2 max-size-bytes=0 max-size-time=0 leaky=downstream '
                  f'! videoconvert ! video/x-raw,format=I420 ! {encoder} '
                  '! h264parse ! rtph264pay name=pay0 pt=96 config-interval=1 )')
        # Validate syntax/plugins now instead of silently failing on first client.
        pipeline = Gst.parse_launch(launch)
        pipeline.set_state(Gst.State.NULL)
        self.server = GstRtspServer.RTSPServer.new()
        self.server.set_address(config['bind'])
        self.server.set_service(str(config['port']))
        self.factory = GstRtspServer.RTSPMediaFactory.new()
        self.factory.set_launch(launch)
        self.factory.set_shared(True)
        self.factory.connect('media-configure', self._configure)
        self.server.get_mount_points().add_factory(config['mount'], self.factory)
        self.loop = GLib.MainLoop()
        self.source_id = 0

    def _configure(self, factory, media):
        Gst, cfg = self.Gst, self.config
        appsrc = media.get_element().get_by_name('source')
        caps = Gst.Caps.from_string(
            f'video/x-raw,format=BGR,width={cfg["width"]},height={cfg["height"]},framerate={cfg["fps"]}/1')
        appsrc.set_property('caps', caps)
        state = {'index': 0, 'next_at': time.monotonic()}

        def need_data(source, length):
            try:
                import cv2
                import numpy as np
                delay = state['next_at'] - time.monotonic()
                if delay > 0:
                    self.stop.wait(delay)
                state['next_at'] = max(state['next_at'] + 1 / cfg['fps'], time.monotonic())
                _, frame = self.frames.read()
                if frame is None:
                    return  # capture is started and validated before the service
                if self.stop.is_set() or time.monotonic() - frame.captured_at > 1:
                    source.emit('end-of-stream')
                    return
                image = frame.bgr
                if image.shape[:2] != (cfg['height'], cfg['width']):
                    image = cv2.resize(image, (cfg['width'], cfg['height']))
                data = np.ascontiguousarray(image).tobytes()
                buffer = Gst.Buffer.new_allocate(None, len(data), None)
                buffer.fill(0, data)
                buffer.pts = state['index'] * Gst.SECOND // cfg['fps']
                buffer.duration = Gst.SECOND // cfg['fps']
                state['index'] += 1
                ret = source.emit('push-buffer', buffer)
                if ret not in (Gst.FlowReturn.OK, Gst.FlowReturn.FLUSHING):
                    LOG.warning('RTSP push returned %s', ret)
            except Exception:
                LOG.exception('RTSP frame failed; terminating this media session')
                source.emit('end-of-stream')

        appsrc.connect('need-data', need_data)

    def start(self):
        self.source_id = self.server.attach(None)
        if not self.source_id:
            raise RuntimeError('Cannot bind RTSP server; check address/port')
        self.thread = threading.Thread(target=self.loop.run, name='rtsp', daemon=True)
        self.thread.start()
        LOG.info('RTSP raw video: rtsp://<board-ip>:%s%s', self.config['port'], self.config['mount'])

    def close(self):
        if self.source_id:
            self.GLib.source_remove(self.source_id)
            self.source_id = 0
        self.loop.quit()
        if self.thread:
            self.thread.join(timeout=2)

