"""
Streaming parsers for real-time agent response processing
Handles JSON streaming for answers and flashcards
"""
import json


class AnswerStreamer:
    """Stream a single JSON string value for key "answer"."""
    KEY = '"answer"'

    def __init__(self):
        self.in_answer = False
        self.finished = False
        self.start_idx = -1   # index of first char INSIDE the string
        self.stream_pos = 0   # how many chars from the answer we've emitted

    @staticmethod
    def _find_start(buf: str, search_from: int) -> int:
        k = buf.find(AnswerStreamer.KEY, search_from)
        if k == -1:
            return -1
        colon = buf.find(":", k + len(AnswerStreamer.KEY))
        if colon == -1:
            return -1
        q = buf.find('"', colon + 1)
        return -1 if q == -1 else q + 1

    @staticmethod
    def _scan_to_close(buf: str, start: int):
        """
        Scan forward from `start` (inside a JSON string) until we find the closing quote.
        Returns (end_pos_exclusive, raw_piece, finished_bool).
        raw_piece is the newly available raw substring (without closing quote).
        """
        i = start
        escaped = False
        while i < len(buf):
            c = buf[i]
            if escaped:
                escaped = False
            elif c == '\\':
                escaped = True
            elif c == '"':
                return i + 1, buf[start:i], True
            i += 1
        return i, buf[start:], False

    def feed(self, global_buf: str, prev_len: int):
        """Yield decoded text chunks as they become available."""
        if self.finished:
            return []
        out = []

        # enter answer mode if not yet
        if not self.in_answer:
            start = self._find_start(global_buf, 0)  # search entire buffer for robustness
            if start != -1:
                self.in_answer = True
                self.start_idx = start
                self.stream_pos = 0

        # if inside answer, stream what's new
        if self.in_answer:
            abs_pos = self.start_idx + self.stream_pos
            if abs_pos < len(global_buf):
                end_pos, raw_piece, done = self._scan_to_close(global_buf, abs_pos)
                if raw_piece:
                    try:
                        out.append(json.loads(f'"{raw_piece}"'))
                    except Exception:
                        out.append(raw_piece)
                    self.stream_pos += len(raw_piece)
                if done:
                    self.in_answer = False
                    self.finished = True
                    self.stream_pos += 1  # closing quote
        return out


class FlashcardStreamer:
    """Stream objects inside the JSON array under key "flashcards" using a raw_decode loop."""
    KEY = '"flashcards"'

    def __init__(self):
        self.started = False
        self.done = False
        self.buf = ""                  # everything after the '[' of the array
        self.decoder = json.JSONDecoder()

    @staticmethod
    def _find_array_lb(buf: str, search_from: int) -> int:
        k = buf.find(FlashcardStreamer.KEY, search_from)
        if k == -1:
            return -1
        lb = buf.find("[", k)
        return lb

    def _extract(self):
        """Return list of parsed objs, update self.buf, and set done when ']' hit."""
        out = []
        s = self.buf.lstrip(", \n")
        while s:
            # array end?
            if s and s[0] == ']':
                self.done = True
                s = s[1:]  # drop the ']'
                break
            # not starting at object? skip one char
            if s and s[0] != '{':
                s = s[1:]
                continue
            # try to decode one object
            try:
                obj, consumed = self.decoder.raw_decode(s)
            except ValueError:
                # need more data
                break
            out.append(obj)
            s = s[consumed:].lstrip(", \n")
        self.buf = s
        return out

    def feed(self, global_buf: str, prev_len: int, new_chunk: str):
        """Yield flashcard dicts as they complete."""
        if self.done:
            return []

        out = []
        # detect start of array once
        if not self.started:
            lb = self._find_array_lb(global_buf, max(0, prev_len - 64))
            if lb != -1:
                self.started = True
                # push everything after '[' into buffer
                self.buf += global_buf[lb + 1:]
                out.extend(self._extract())
                return out

        # if already started, just append the new chunk and parse
        if self.started and not self.done:
            self.buf += new_chunk
            out.extend(self._extract())

        return out