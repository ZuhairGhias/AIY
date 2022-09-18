#!/usr/bin/env python3
import contextlib
import sys
import logging
from time import sleep
from picamera import PiCamera
from aiy.vision.streaming.server import StreamingServer
from aiy.vision.streaming import svg
from aiy.vision.inference import CameraInference
from aiy.vision.models import face_detection
from aiy.toneplayer import TonePlayer
from aiy.leds import Color, Leds, Pattern, PrivacyLed
from services import Player, Photographer

logger = logging.getLogger(__name__)

JOY_SOUND = ('C5q', 'E5q', 'C6q')
SAD_SOUND = ('C6q', 'E5q', 'C5q')
MODEL_LOAD_SOUND = ('C6w', 'c6w', 'C6w')
BEEP_SOUND = ('E6q', 'C6q')

GREEN_COLOR = (0, 255, 0)
RED_COLOR = (255, 0, 0)

BUZZER_GPIO = 22

IMAGE_FORMAT = "jpeg"
IMAGE_FOLDER = "./captures"

SLEEP_SECONDS = 600


def run_inference():
    """Yields (faces, (frame_width, frame_height)) tuples."""
    with CameraInference(face_detection.model()) as inference:
        print('Model loaded')
        TonePlayer(gpio=BUZZER_GPIO, bpm=10).play(*MODEL_LOAD_SOUND)
        for result in inference.run():
            yield face_detection.get_faces(result), (result.width, result.height)


def capture_loop():
    with contextlib.ExitStack() as stack:
        leds = stack.enter_context(Leds())
        camera = stack.enter_context(PiCamera(sensor_mode=4, resolution=(820, 616)))
        stack.enter_context(PrivacyLed(leds))
        player = stack.enter_context(Player(BUZZER_GPIO,10))
        photographer = stack.enter_context(Photographer(IMAGE_FORMAT,IMAGE_FOLDER))
        server = StreamingServer(camera)  # http://raspberrypi.local:4664/
        print("server running...")

        for faces, frame_size in run_inference():
            if faces:
                player.play(BEEP_SOUND)
                photographer.update_faces((faces, frame_size))
                photographer.shoot(camera)
                print(faces)
                print(frame_size)
                sleep(SLEEP_SECONDS)


def main():
    logging.basicConfig(level=logging.INFO)

    try:
        capture_loop()
    except KeyboardInterrupt:
        pass
    except Exception:
        logger.exception('Exception while running joy demo.')
        with Leds() as leds:
            leds.pattern = Pattern.blink(100)  # 10 Hz
            leds.update(Leds.rgb_pattern(Color.RED))
            sleep(1.0)

    return 0


if __name__ == "__main__":
    sys.exit(main())