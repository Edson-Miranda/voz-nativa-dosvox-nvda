# -*- coding: UTF-8 -*-
import addonHandler
import config
import logHandler
import os
import queue
import re
import sys
import threading

import nvwave
import synthDriverHandler
from speech.commands import SynthCommand
from speech.extensions import filter_speechSequence

addonHandler.initTranslation()
log = logHandler.log
VERBOSE_LOGGING = False
TEXT_SYNTH_CHUNK_CHARS = 40
SPEECH_START_PREROLL_MS = 20
SAMPLE_RATE = 11025
SILENCE_SAMPLE_8BIT = b"\x80"

MODULE_DIR = os.path.dirname(__file__)
if MODULE_DIR not in sys.path:
    sys.path.insert(0, MODULE_DIR)

from dosvox_native_core import DosvoxNativeSynth, get_available_voices  # noqa: E402
from dosvox_native_core import get_available_voice_variants  # noqa: E402
from dosvox_native_core import resolve_named_key  # noqa: E402
from dosvox_native_core import split_source_symbols  # noqa: E402


class DosvoxSourceSymbolCommand(SynthCommand):
    """Carries a real source symbol past NVDA's name expansion."""

    def __init__(self, character):
        self.character = character

    def __repr__(self):
        return "DosvoxSourceSymbolCommand(%r)" % self.character


class SynthDriver(synthDriverHandler.SynthDriver):
    name = "vozNativaDoDosvox"
    description = _("Voz nativa do dosvox")

    supportedSettings = [
        synthDriverHandler.SynthDriver.RateSetting(),
        synthDriverHandler.SynthDriver.VariantSetting(),
    ]
    supportedCommands = {DosvoxSourceSymbolCommand}

    @classmethod
    def check(cls):
        return bool(get_available_voices(MODULE_DIR))

    def __init__(self):
        self._rate = 50
        self._voice = "dosvoxNative"
        self._variant = "Difones2"
        self._queue = queue.Queue()
        self._cancel_event = threading.Event()
        self._state_lock = threading.RLock()
        self._generation = 0
        self._player_lock = threading.RLock()
        self._output_device = self._get_configured_output_device()
        self._player = self._create_player(self._output_device)
        self._playback_id = 0
        variants = self.availableVariants
        if not variants:
            raise RuntimeError("Nenhuma voz Dosvox encontrada no addon.")
        if self._variant not in variants:
            self._variant = next(iter(variants))
        self._engine = DosvoxNativeSynth(MODULE_DIR, self._variant)
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()
        filter_speechSequence.register(self._preserve_source_symbols)

    def _preserve_source_symbols(self, speech_sequence):
        """Mark real symbols while they still differ from written names."""
        try:
            symbol_level = int(config.conf["speech"]["symbolLevel"])
        except Exception:
            symbol_level = 300
        marked = []
        character_mode = False
        total = len(speech_sequence)
        for index, item in enumerate(speech_sequence):
            if item.__class__.__name__ == "CharacterModeCommand":
                character_mode = bool(
                    getattr(item, "state", getattr(item, "enable", getattr(item, "enabled", False)))
                )
                marked.append(item)
                continue
            if not isinstance(item, str) or character_mode:
                marked.append(item)
                continue
            # speakSpelling expands a typed symbol to its localized name
            # before this filter (for example, "." becomes "ponto"). Unlike
            # ordinary text, that name is immediately followed by an
            # EndUtteranceCommand, which preserves its spelling origin.
            next_is_spelling_end = (
                index + 1 < total
                and speech_sequence[index + 1].__class__.__name__ == "EndUtteranceCommand"
            )
            if next_is_spelling_end and item.strip() == item:
                resolved = resolve_named_key(item)
                if resolved is not None and resolved[0] == "character":
                    marked.append(DosvoxSourceSymbolCommand(resolved[1]))
                    continue
            for kind, value in split_source_symbols(item, symbol_level):
                if kind == "symbol":
                    marked.append(DosvoxSourceSymbolCommand(value))
                elif value:
                    marked.append(value)
        return marked

    def _get_availableVoices(self):
        return {
            voice_id: synthDriverHandler.VoiceInfo(voice_id, label)
            for voice_id, label in get_available_voices(MODULE_DIR).items()
        }

    def _get_voice(self):
        return self._voice

    def _set_voice(self, value):
        if value in self.availableVoices:
            self._voice = value

    def _get_availableVariants(self):
        return {
            variant_id: synthDriverHandler.VoiceInfo(variant_id, label)
            for variant_id, label in get_available_voice_variants(MODULE_DIR).items()
        }

    def _get_variant(self):
        return self._variant

    def _set_variant(self, value):
        variants = self.availableVariants
        if value not in variants:
            return
        self._variant = value
        self._engine = DosvoxNativeSynth(MODULE_DIR, self._variant)

    def _get_rate(self):
        return self._rate

    def _set_rate(self, value):
        self._rate = max(0, min(100, int(value)))

    def _get_configured_output_device(self):
        try:
            return config.conf["audio"]["outputDevice"]
        except Exception:
            pass
        try:
            return config.conf["speech"]["outputDevice"]
        except Exception:
            return None

    def _create_player(self, output_device):
        kwargs = {
            "channels": 1,
            "samplesPerSec": SAMPLE_RATE,
            "bitsPerSample": 8,
            "buffered": True,
        }
        if output_device is not None:
            kwargs["outputDevice"] = output_device
        try:
            return nvwave.WavePlayer(**kwargs)
        except TypeError:
            kwargs.pop("buffered", None)
            return nvwave.WavePlayer(**kwargs)

    def _stop_player_instance(self, player):
        try:
            player.stop()
        except Exception:
            pass

    def _stop_player_async(self, player):
        threading.Thread(target=self._stop_player_instance, args=(player,), daemon=True).start()

    def _reset_player_for_interrupt(self):
        output_device = self._get_configured_output_device()
        try:
            new_player = self._create_player(output_device)
        except Exception:
            with self._player_lock:
                old_player = self._player
            self._stop_player_instance(old_player)
            return
        with self._player_lock:
            old_player = self._player
            self._player = new_player
            self._output_device = output_device
        self._stop_player_async(old_player)

    def _stop_player(self):
        with self._player_lock:
            player = self._player
        self._stop_player_instance(player)

    def _discard_pending_speech(self):
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def _interrupt_current_speech(self):
        with self._state_lock:
            self._generation += 1
            self._playback_id += 1
            self._cancel_event.set()
        self._discard_pending_speech()
        self._reset_player_for_interrupt()

    def _queue_speech(self, segments, indexes):
        with self._state_lock:
            self._cancel_event.clear()
            generation = self._generation
        self._queue.put((segments, indexes, generation))

    def _is_cancelled(self, generation):
        with self._state_lock:
            return self._cancel_event.is_set() or generation != self._generation

    def _iter_text_chunks(self, text):
        text = str(text or "")
        if len(text) <= TEXT_SYNTH_CHUNK_CHARS:
            if text:
                yield text
            return
        current = []
        current_len = 0
        for token in re.findall(r"\S+\s*", text, re.UNICODE):
            token_len = len(token)
            if current and current_len + token_len > TEXT_SYNTH_CHUNK_CHARS:
                yield "".join(current)
                current = []
                current_len = 0
            current.append(token)
            current_len += token_len
            if current_len >= 20 and re.search(r"[.!?;:]\s*$", token, re.UNICODE):
                yield "".join(current)
                current = []
                current_len = 0
        if current:
            yield "".join(current)

    def _synthesize_pcm_chunks(self, segment_type, value, symbol_level):
        if segment_type == "character":
            pcm = self._engine.synthesize_character(
                value,
                rate=self._rate,
            )
            if pcm:
                yield pcm
            return
        for text_chunk in self._iter_text_chunks(value):
            pcm = self._engine.synthesize_text(
                text_chunk,
                rate=self._rate,
                pause_scale=1.0,
                symbol_level=symbol_level,
            )
            if pcm:
                yield pcm

    def _notify_done(self):
        try:
            synthDriverHandler.synthDoneSpeaking.notify(synth=self)
        except Exception:
            pass

    def _feed_pcm(self, pcm, generation):
        if not pcm:
            return True
        if self._is_cancelled(generation):
            return False
        self._sync_output_device()
        with self._player_lock:
            player = self._player
        if self._is_cancelled(generation):
            return False
        with self._state_lock:
            self._playback_id += 1
        try:
            player.feed(pcm)
        except Exception:
            return False
        return not self._is_cancelled(generation)

    def _prepend_start_preroll(self, pcm):
        if not pcm or SPEECH_START_PREROLL_MS <= 0:
            return pcm
        silence_len = max(1, int(SAMPLE_RATE * SPEECH_START_PREROLL_MS / 1000))
        return (SILENCE_SAMPLE_8BIT * silence_len) + pcm

    def _sync_output_device(self):
        output_device = self._get_configured_output_device()
        if output_device == self._output_device:
            return
        with self._player_lock:
            if output_device == self._output_device:
                return
            try:
                self._player.stop()
            except Exception:
                pass
            self._player = self._create_player(output_device)
            self._output_device = output_device
            log.debug("vozNativaDoDosvox outputDevice=%r", output_device)

    def speakCharacter(self, character, index=None):
        indexes = [index] if index is not None else []
        if VERBOSE_LOGGING:
            log.debug(
                "vozNativaDoDosvox speakCharacter raw=%r ords=%s index=%r",
                character,
                [ord(ch) for ch in character] if isinstance(character, str) else None,
                index,
            )
        resolved = resolve_named_key(character.strip()) if isinstance(character, str) else None
        if VERBOSE_LOGGING:
            log.debug("vozNativaDoDosvox speakCharacter resolved=%r", resolved)
        if resolved is not None:
            kind, value = resolved
            if kind == "character":
                self._queue_speech([("character", value)], indexes)
                return
            if kind == "fkey":
                segments = [("character", "F")]
                segments.extend(("character", digit) for digit in value)
                self._queue_speech(segments, indexes)
                return
        self._queue_speech([("character", character)], indexes)

    def _resolved_text_to_segments(self, text):
        stripped = text.strip()
        if not stripped or stripped != text:
            return None
        resolved = resolve_named_key(stripped)
        if resolved is not None:
            kind, value = resolved
            if kind == "character":
                return [("character", value)]
            if kind == "fkey":
                segments = [("character", "F")]
                segments.extend(("character", digit) for digit in value)
                return segments
        if len(stripped) == 1:
            return [("character", stripped)]
        return None

    def _segments_equal(self, left, right):
        return len(left) == len(right) and all(a == b for a, b in zip(left, right))

    def _resolve_chunk_to_segments(self, chunk):
        stripped = chunk.strip()
        if not stripped:
            return None
        resolved = self._resolved_text_to_segments(stripped)
        if resolved is not None:
            return resolved
        if re.fullmatch(r"[^\w\s]+", stripped, re.UNICODE):
            return [("character", char) for char in stripped]
        trailing = re.match(r"^(.*?)([^\w\s]+)$", stripped, re.UNICODE)
        if trailing:
            prefix = trailing.group(1).strip()
            suffix = trailing.group(2)
            prefix_segments = self._resolved_text_to_segments(prefix) if prefix else None
            if prefix_segments is not None:
                segments = list(prefix_segments)
                segments.extend(("character", char) for char in suffix)
                return segments
        return None

    def _expand_symbol_echo_text(self, text):
        if "  " not in text:
            return None
        chunks = re.split(r"(\s{2,})", text)
        if len(chunks) < 3:
            return None
        resolved_count = 0
        total_non_space = 0
        expanded = []
        for chunk in chunks:
            if not chunk:
                continue
            if chunk.isspace():
                continue
            total_non_space += 1
            resolved = self._resolve_chunk_to_segments(chunk)
            if resolved is not None:
                expanded.extend(resolved)
                resolved_count += 1
            else:
                expanded.append(("text", chunk))
        if resolved_count < 2 or resolved_count < max(2, total_non_space // 2):
            return None
        return expanded

    def _rewrite_short_sequences(self, segments):
        # Normal speech has no reliable metadata saying whether a name such
        # as "ponto" came from punctuation or was actually written. Only the
        # explicit character paths may reinterpret key and symbol names.
        return segments

    def _append_special_segments(self, segments, text):
        segments.append(("text", text))

    def speak(self, speechSequence):
        segments = []
        indexes = []
        extra_pause_marks = 0
        character_mode = False
        if VERBOSE_LOGGING:
            sequence_dump = []
            for item in speechSequence:
                if isinstance(item, str):
                    sequence_dump.append(
                        {
                            "type": "str",
                            "value": item,
                            "ords": [ord(ch) for ch in item],
                        }
                    )
                else:
                    sequence_dump.append(
                        {
                            "type": item.__class__.__name__,
                            "repr": repr(item),
                            "attrs": {
                                "state": getattr(item, "state", None),
                                "enable": getattr(item, "enable", None),
                                "enabled": getattr(item, "enabled", None),
                                "index": getattr(item, "index", None),
                                "time": getattr(item, "time", None),
                            },
                        }
                    )
            log.debug("vozNativaDoDosvox speak speechSequence=%r", sequence_dump)
        for item in speechSequence:
            if isinstance(item, str):
                if character_mode:
                    stripped = item.strip()
                    if stripped:
                        resolved = resolve_named_key(stripped)
                        if resolved is not None:
                            kind, value = resolved
                            if kind == "character":
                                segments.append(("character", value))
                                continue
                            if kind == "fkey":
                                segments.append(("character", "F"))
                                for digit in value:
                                    segments.append(("character", digit))
                                continue
                    for char in item:
                        segments.append(("character", char))
                else:
                    self._append_special_segments(segments, item)
                continue

            class_name = item.__class__.__name__
            if class_name == "DosvoxSourceSymbolCommand":
                segments.append(("character", item.character))
            elif class_name == "BreakCommand":
                extra_pause_marks += max(1, int(getattr(item, "time", 0) / 100))
            elif class_name == "IndexCommand":
                indexes.append(getattr(item, "index", None))
            elif class_name == "CharacterModeCommand":
                character_mode = bool(
                    getattr(item, "state", getattr(item, "enable", getattr(item, "enabled", False)))
                )
        if extra_pause_marks:
            segments.append(("text", " " + (". " * extra_pause_marks)))
        segments = self._rewrite_short_sequences(segments)
        if VERBOSE_LOGGING:
            log.debug("vozNativaDoDosvox speak characterMode=%r segments=%r indexes=%r", character_mode, segments, indexes)
        if not segments or not any(value for _, value in segments):
            self._notify_done()
            return
        self._queue_speech(segments, indexes)

    def cancel(self):
        self._interrupt_current_speech()
        self._notify_done()

    def pause(self, switch):
        with self._player_lock:
            if hasattr(self._player, "pause"):
                self._player.pause(switch)

    def terminate(self):
        try:
            filter_speechSequence.unregister(self._preserve_source_symbols)
        except Exception:
            pass
        with self._state_lock:
            self._generation += 1
            self._playback_id += 1
            self._cancel_event.set()
        self._queue.put(None)
        self._reset_player_for_interrupt()

    def _run(self):
        while True:
            item = self._queue.get()
            if item is None:
                return
            segments, indexes, generation = item
            if self._is_cancelled(generation):
                continue
            spoke = False
            fed_any_pcm = False
            try:
                try:
                    symbol_level = int(config.conf["speech"]["symbolLevel"])
                except Exception:
                    symbol_level = 300
                for segment_type, value in segments:
                    if self._is_cancelled(generation):
                        break
                    for pcm in self._synthesize_pcm_chunks(segment_type, value, symbol_level):
                        if self._is_cancelled(generation):
                            break
                        if indexes:
                            for index in indexes:
                                if index is not None:
                                    synthDriverHandler.synthIndexReached.notify(synth=self, index=index)
                            indexes = []
                        if not fed_any_pcm:
                            pcm = self._prepend_start_preroll(pcm)
                        if self._feed_pcm(pcm, generation):
                            spoke = True
                            fed_any_pcm = True
                        else:
                            break
                    if self._is_cancelled(generation):
                        break
                if spoke:
                    self._notify_done()
            finally:
                if not spoke:
                    self._notify_done()
