# -*- coding: utf-8 -*-

import codecs
import subprocess
from tempfile import NamedTemporaryFile

from ikazuchi.core.handler.base import BaseHandler
from ikazuchi.core.handler.utils import get_and_check_file_access
from ikazuchi.core.translator import TRANSLATE_API as API
from ikazuchi.ikazuchi import (base_parser, subparsers)
from ikazuchi.utils import get_command

_MACOS_COMMANDS   = ["afplay", "mpg123", "gst123", "mpg321"]
_LINUX_COMMANDS   = ["mpg123", "gst123", "mpg321"]
_WINDOWS_COMMANDS = []

# argument parser for speech
speech_parser = subparsers.add_parser("speech", parents=[base_parser])
speech_parser.set_defaults(command=None, post=False, read=None, sentences=[])
speech_parser.add_argument("-c", "--command", dest="command",
    metavar="COMMAND", help="use any command to speak(play audio file)")
speech_parser.add_argument("-p", "--post", dest="post", action="store_true",
    help="speak post-translated target sentences")
speech_parser.add_argument("-r", "--read", dest="read",
    metavar="READING TARGET FILE", help="read aloud target file")
speech_parser.add_argument("-s", "--sentences", dest="sentences", nargs="+",
    metavar="SENTENCE", help=u"target sentences")

class Handler(BaseHandler):
    """
    Handler class for text-to-speech
    """
    def __init__(self, opts):
        self.api = opts.api
        self.command = opts.command
        self.encoding = opts.encoding
        self.sentences = opts.sentences
        self.read_file = opts.read
        self.quiet = opts.quiet
        self.lang = opts.lang_from
        self.post = opts.post
        self.translator = API[opts.api](opts.lang_from, opts.lang_to, None)
        if self.post:
            self.lang = opts.lang_to
        if self.api == "google":
            self.method_name = "translate_tts"
        elif self.api == "microsoft":
            self.method_name = "speak"

    def _encode(self, text):
        return text.encode(self.encoding[1])

    def _translate(self, texts):
        if self.api == "google":
            api, translated = self.translator.translate(texts)
        elif self.api == "microsoft":
            api, translated = self.translator.translate_array(texts)
        return translated

    def _call_method(self, api_method):
        orig_texts = self._get_target_texts()
        if self.post:
            texts = self._translate(orig_texts)
        else:
            texts = orig_texts
        _trans = u"{0}({1}):".format("translate", self.api.title())
        for num, text in enumerate(texts):
            if not self.quiet:
                print self._encode(u"{0:25}{1}".format(
                            "sentence:", orig_texts[num]))
            if self.post:
                print self._encode(u"{0:25}{1}".format(_trans, text))
            with NamedTemporaryFile(mode="wb") as tmp:
                api = api_method(text, self.lang, tmp)
                _method = u"{0}({1}):".format(self.method_name, api)
                print self._encode(u"{0:25}".format(_method))
                self.play_audio(tmp.name)

    def _get_target_texts(self):
        texts = self.sentences
        if self.read_file:
            rf = get_and_check_file_access(self.read_file)
            with codecs.open(rf, mode="r", encoding=self.encoding[1]) as f:
                texts = [line.rstrip() for line in f if line.rstrip()]
        return texts

    def _get_play_audio_command(self):
        import platform
        os_name, commands = platform.system(), []
        if os_name == "Darwin":
            commands = _MACOS_COMMANDS
        elif os_name == "Windows":
            commands = _WINDOWS_COMMANDS
        elif os_name in ("Linux", "FreeBSD"):
            commands = _LINUX_COMMANDS
        return [path for cmd in commands for path in get_command(cmd)]

    def play_audio(self, file_name):
        if self.command:
            subprocess.call([self.command, file_name])
        else:
            cmd = self._get_play_audio_command()
            if cmd:
                subprocess.call([cmd[0], file_name])
            else:
                play_audio_with_pyglet(file_name)

    def play_audio_with_pyglet(self, file_name):
        import pyglet
        media = pyglet.media.load(file_name, streaming=False)
        pyglet.clock.schedule_once(lambda d: pyglet.app.exit(), media.duration)
        media.play()
        pyglet.app.run()

    def play_with_ossaudiodev(self, file_name):
        import sys
        import sndhdr
        from contextlib import closing, nested
        from ossaudiodev import open as oss_open
        from wave import open as wave_open
        file_info = sndhdr.what(file_name)
        if not file_info or file_info[0] != "wav":
            print "Not supported audio file type"
            return
        with nested(closing(wave_open(file_name, "rb")),
                    closing(oss_open("w"))) as (wav, dev):
            nc, sw, fr, nf, comptype, compname = wav.getparams()
            try:
                from ossaudiodev import (AFMT_S16_NE, AFMT_S16_BE, AFMT_S16_LE)
            except ImportError:
                AFMT_S16_NE = AFMT_S16_BE
                if sys.byteorder == "little":
                    AFMT_S16_NE = AFMT_S16_LE
            dev.setparameters(AFMT_S16_NE, nc, fr)
            data = wav.readframes(nf)
            dev.write(data)
