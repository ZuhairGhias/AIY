import contextlib
import io
import logging
import os
import queue
import threading
import time

from PIL import Image, ImageDraw, ImageFont

from aiy.leds import Color, Leds
from aiy.toneplayer import TonePlayer

logger = logging.getLogger(__name__)

JOY_COLOR = (255, 70, 0)
SAD_COLOR = (0, 0, 64)

JOY_SCORE_HIGH = 0.85
JOY_SCORE_LOW = 0.10

JOY_SOUND = ('C5q', 'E5q', 'C6q')
SAD_SOUND = ('C6q', 'E5q', 'C5q')
MODEL_LOAD_SOUND = ('C6w', 'c6w', 'C6w')
BEEP_SOUND = ('E6q', 'C6q')

FONT_FILE = '/usr/share/fonts/truetype/freefont/FreeSans.ttf'

BUZZER_GPIO = 22


@contextlib.contextmanager
def stopwatch(message):
    try:
        logger.info('%s...', message)
        begin = time.monotonic()
        yield
    finally:
        end = time.monotonic()
        logger.info('%s done. (%fs)', message, end - begin)


def draw_rectangle(draw, x0, y0, x1, y1, border, fill=None, outline=None):
    assert border % 2 == 1
    for i in range(-border // 2, border // 2 + 1):
        draw.rectangle((x0 + i, y0 + i, x1 - i, y1 - i), fill=fill, outline=outline)


def scale_bounding_box(bounding_box, scale_x, scale_y):
    x, y, w, h = bounding_box
    return (x * scale_x, y * scale_y, w * scale_x, h * scale_y)


def bounding_extent_to_corners(bounding_box, image_size):
    x, y, width, height = bounding_box
    left = x
    upper = y
    right = x + width
    lower = y + height
    return left, upper, right, lower


class Service:

    def __init__(self):
        self._requests = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        while True:
            request = self._requests.get()
            if request is None:
                self.shutdown()
                break
            self.process(request)
            self._requests.task_done()

    def process(self, request):
        pass

    def shutdown(self):
        pass

    def submit(self, request):
        self._requests.put(request)

    def close(self):
        self._requests.put(None)
        self._thread.join()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.close()


class Player(Service):
    """Controls buzzer."""

    def __init__(self, gpio, bpm):
        super().__init__()
        self._toneplayer = TonePlayer(gpio, bpm)

    def process(self, sound):
        self._toneplayer.play(*sound)

    def play(self, sound):
        self.submit(sound)


class Photographer(Service):
    """Saves photographs to disk."""

    def __init__(self, format, folder):
        super().__init__()
        assert format in ('jpeg', 'bmp', 'png')

        self._font = ImageFont.truetype(FONT_FILE, size=25)
        self._faces = ([], (0, 0))
        self._format = format
        self._folder = folder
        #if not os.path.exists(os.path.expanduser(self._folder)):
        #    os.mkdir(os.path.expanduser(self._folder))

    def _make_filename(self, timestamp, suffix=""):
        path = '%s/%s_%s.%s' if len(suffix) > 0 else '%s/%s%s.%s'
        return os.path.expanduser(path % (self._folder, timestamp, suffix, self._format))

    def _draw_face(self, draw, face, scale_x, scale_y):
        x, y, width, height = scale_bounding_box(face.bounding_box, scale_x, scale_y)
        text = 'Joy: %.2f' % face.joy_score
        _, text_height = self._font.getsize(text)
        margin = 3
        bottom = y + height
        text_bottom = bottom + margin + text_height + margin
        draw_rectangle(draw, x, y, x + width, bottom, 3, outline='white')
        draw_rectangle(draw, x, bottom, x + width, text_bottom, 3, fill='white', outline='white')
        draw.text((x + 1 + margin, y + height + 1 + margin), text, font=self._font, fill='black')

    def process(self, message):
        if isinstance(message, tuple):
            self._faces = message
            return

        camera = message
        timestamp = time.strftime('%Y-%m-%d_%H.%M.%S')

        stream = io.BytesIO()
        with stopwatch('Taking photo'):
            camera.capture(stream, format=self._format, use_video_port=True)

        filename = self._make_filename(timestamp)
        with stopwatch('Saving original %s' % filename):
            stream.seek(0)
            with open(filename, 'wb') as file:
                file.write(stream.read())

        faces, (width, height) = self._faces
        if faces:
            filename1 = self._make_filename(timestamp, "annotated")
            filename2 = self._make_filename(timestamp, "cropped")
            with stopwatch('Saving annotated %s' % filename):
                stream.seek(0)
                image = Image.open(stream)
                draw = ImageDraw.Draw(image)
                scale_x, scale_y = image.width / width, image.height / height
                for face in faces:
                    scaled = scale_bounding_box(face.bounding_box, scale_x, scale_y)
                    corners = bounding_extent_to_corners(scaled, image.size)
                    image2 = image.crop(corners)
                    self._draw_face(draw, face, scale_x, scale_y)
                del draw
                #image.save(filename1)
                image2.save(filename2)

    def update_faces(self, faces):
        self.submit(faces)

    def shoot(self, camera):
        self.submit(camera)


class Animator(Service):
    """Controls RGB LEDs."""

    def __init__(self, leds):
        super().__init__()
        self._leds = leds

    def process(self, joy_score):
        if joy_score > 0:
            self._leds.update(Leds.rgb_on(Color.blend(JOY_COLOR, SAD_COLOR, joy_score)))
        else:
            self._leds.update(Leds.rgb_off())

    def shutdown(self):
        self._leds.update(Leds.rgb_off())

    def update_joy_score(self, joy_score):
        self.submit(joy_score)
