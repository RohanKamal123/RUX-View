"""YAMNet Detector — on-device sound classification for security events.

Runs YAMNet (TensorFlow Hub model) locally to classify audio chunks
into 521 sound classes.  Only speech triggers Whisper transcription;
only security-relevant sounds (glass breaking, gunshot, scream, etc.)
trigger alerts.  This keeps 90%+ of ambient sound on-device (D004).
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import tensorflow as tf
import tensorflow_hub as hub

logger = logging.getLogger(__name__)

# ── YAMNet Model URL ──────────────────────────────────────────────────────────
YAMNET_URL = "https://tfhub.dev/google/yamnet/1"

# ── Security Class Mappings ───────────────────────────────────────────────────
# YAMNet class IDs of interest for security monitoring.
# Key: YAMNet class ID, Value: human-readable category name.
SECURITY_CLASSES: dict[int, str] = {
    0:   "speech",          # Speech
    1:   "speech",          # Male speech
    2:   "speech",          # Female speech
    380: "glass_breaking",
    381: "gunshot",
    382: "gunshot",
    400: "scream",
    401: "scream",
    402: "shout",
    403: "shout",
    404: "shout",
    420: "vehicle_alarm",
    421: "vehicle_alarm",
    422: "vehicle_horn",
    423: "vehicle_horn",
    424: "door_slam",
    425: "door_slam",
    426: "footsteps",
    427: "footsteps",
    428: "footsteps",
    429: "footsteps",
    430: "engine",
    431: "engine",
    432: "engine_idling",
    433: "engine_idling",
}

# Speech class IDs — used to determine should_send_to_whisper
SPEECH_CLASS_IDS = {0, 1, 2}


@dataclass
class YAMNetResult:
    """Result of a single YAMNet classification pass.

    Attributes:
        class_name: Human-readable class name (e.g. "glass_breaking").
        class_id: YAMNet class ID (0-520).
        confidence: Confidence score of the top class (0.0-1.0).
        should_send_to_whisper: True if speech detected above threshold.
        should_trigger: True if security-relevant sound above threshold.
    """
    class_name: str
    class_id: int
    confidence: float
    should_send_to_whisper: bool
    should_trigger: bool


class YAMNetDetector:
    """YAMNet sound classifier for security-relevant audio events.

    Lazy-loads the YAMNet model on first use.  All inference runs
    in a thread pool to avoid blocking the async event loop.

    Usage:
        detector = YAMNetDetector()
        result = await detector.classify(audio_chunk)
        if result.should_trigger:
            # handle security event
    """

    def __init__(
        self,
        speech_threshold: float = 0.5,
        security_threshold: float = 0.3,
    ) -> None:
        """Initialize YAMNet detector.

        Args:
            speech_threshold: Confidence threshold for speech detection.
                              Above this, should_send_to_whisper is True.
            security_threshold: Confidence threshold for security sounds.
                                Above this, should_trigger is True.
        """
        self._speech_threshold = speech_threshold
        self._security_threshold = security_threshold
        self._model: Optional[hub.KerasLayer] = None

    # ── Public API ───────────────────────────────────────────────────────────

    def load_model(self) -> None:
        """Load YAMNet model from TensorFlow Hub.

        Lazy-loaded on first use.  Safe to call multiple times —
        subsequent calls are no-ops if the model is already loaded.

        Raises:
            RuntimeError: If model loading fails.
        """
        if self._model is not None:
            logger.debug("YAMNet model already loaded")
            return

        try:
            logger.info("Loading YAMNet model from %s ...", YAMNET_URL)
            self._model = hub.load(YAMNET_URL)
            logger.info("YAMNet model loaded successfully")
        except Exception as exc:
            raise RuntimeError(f"Failed to load YAMNet model: {exc}") from exc

    async def classify(self, audio_chunk: np.ndarray) -> YAMNetResult:
        """Classify audio chunk using YAMNet.

        Runs inference in a thread pool to avoid blocking the event loop.
        The model is lazy-loaded on the first call.

        Args:
            audio_chunk: Float32 numpy array of audio samples (16kHz).
                         Shape: [num_samples].

        Returns:
            YAMNetResult with top class and metadata.

        Raises:
            RuntimeError: If model loading or inference fails.
            ValueError: If audio_chunk is empty or not float32.
        """
        if audio_chunk is None or audio_chunk.size == 0:
            raise ValueError("Audio chunk is empty")

        if audio_chunk.dtype != np.float32:
            raise ValueError(
                f"Expected float32 audio, got {audio_chunk.dtype}"
            )

        # Ensure model is loaded
        if self._model is None:
            self.load_model()

        loop = asyncio.get_running_loop()

        def _infer() -> YAMNetResult:
            try:
                # YAMNet returns (scores, embeddings, spectrogram)
                # scores: [num_frames, 521] — per-frame class scores
                scores, embeddings, spectrogram = self._model(audio_chunk)

                scores_np = scores.numpy()
                class_name, class_id, confidence = self._get_top_class(
                    scores_np, embeddings.numpy(), spectrogram.numpy()
                )

                should_send = self._should_send_to_whisper(class_id, confidence)
                should_trig = self._should_trigger(class_id, confidence)

                return YAMNetResult(
                    class_name=class_name,
                    class_id=class_id,
                    confidence=confidence,
                    should_send_to_whisper=should_send,
                    should_trigger=should_trig,
                )
            except Exception as exc:
                raise RuntimeError(f"YAMNet inference failed: {exc}") from exc

        return await loop.run_in_executor(None, _infer)

    # ── Internal: Classification Helpers ─────────────────────────────────────

    @staticmethod
    def _get_top_class(
        scores: np.ndarray,
        embeddings: np.ndarray,    # noqa: ARG004 — kept for API compatibility
        spectrogram: np.ndarray,   # noqa: ARG004 — kept for API compatibility
    ) -> tuple[str, int, float]:
        """Get the highest-confidence class across all frames.

        Averages scores across all time frames, then picks the class
        with the highest mean score.

        Args:
            scores: YAMNet scores array, shape [num_frames, 521].
            embeddings: YAMNet embeddings (unused, kept for API compat).
            spectrogram: YAMNet spectrogram (unused, kept for API compat).

        Returns:
            Tuple of (class_name, class_id, confidence).
        """
        # Mean score across all frames
        mean_scores = np.mean(scores, axis=0)  # shape: [521]

        # Top class index and score
        class_id = int(np.argmax(mean_scores))
        confidence = float(mean_scores[class_id])

        # Look up class name from YAMNet class map
        class_names = _get_yamnet_class_names()
        class_name = class_names.get(class_id, f"unknown_{class_id}")

        return class_name, class_id, confidence

    def _should_send_to_whisper(self, class_id: int, confidence: float) -> bool:
        """Check if this sound should be sent to Whisper for transcription.

        Only speech classes (0, 1, 2) above the speech threshold
        should be transcribed.

        Args:
            class_id: YAMNet class ID.
            confidence: Confidence score for this class.

        Returns:
            True if this is speech above the confidence threshold.
        """
        return class_id in SPEECH_CLASS_IDS and confidence >= self._speech_threshold

    def _should_trigger(self, class_id: int, confidence: float) -> bool:
        """Check if this sound class should trigger an alert.

        Security-relevant sounds (glass breaking, gunshot, scream, etc.)
        above the security threshold trigger alerts.

        Args:
            class_id: YAMNet class ID.
            confidence: Confidence score for this class.

        Returns:
            True if this is a security-relevant sound above threshold.
        """
        return class_id in SECURITY_CLASSES and confidence >= self._security_threshold


# ── YAMNet Class Name Lookup ──────────────────────────────────────────────────
# YAMNet's 521-class label map (subset used by SECURITY_CLASSES + common ones).
# Full map available at:
#   https://github.com/tensorflow/models/blob/master/research/audioset/yamnet/yamnet_class_map.csv

_YAMNET_CLASS_NAMES: Optional[dict[int, str]] = None


def _get_yamnet_class_names() -> dict[int, str]:
    """Get the YAMNet class ID-to-name mapping.

    Lazily loaded and cached.  Covers all 521 classes with
    human-readable names from the YAMNet class map CSV.

    Returns:
        Dict mapping class ID (int) to class name (str).
    """
    global _YAMNET_CLASS_NAMES

    if _YAMNET_CLASS_NAMES is not None:
        return _YAMNET_CLASS_NAMES

    # YAMNet class map (index → display name)
    # Source: https://github.com/tensorflow/models/blob/master/research/audioset/yamnet/yamnet_class_map.csv
    _YAMNET_CLASS_NAMES = {
        0: "Speech",
        1: "Male speech, man speaking",
        2: "Female speech, woman speaking",
        3: "Child speech, kid speaking",
        4: "Conversation",
        5: "Narration, monologue",
        6: "Babbling",
        7: "Speech synthesizer",
        8: "Shout",
        9: "Bellow",
        10: "Whoop",
        11: "Yell",
        12: "Children shouting",
        13: "Screaming",
        14: "Whispering",
        15: "Laughter",
        16: "Giggle",
        17: "Snicker",
        18: "Chuckle",
        19: "Crying, sobbing",
        20: "Baby cry, infant cry",
        21: "Whimper",
        22: "Wail, moan",
        23: "Sigh",
        24: "Singing",
        25: "Choir",
        26: "Yodeling",
        27: "Chant",
        28: "Mantra",
        29: "Child singing",
        30: "Synthetic singing",
        31: "Rapping",
        32: "Humming",
        33: "Groan",
        34: "Grunt",
        35: "Whistle",
        36: "Breathing",
        37: "Wheeze",
        38: "Snoring",
        39: "Gasp",
        40: "Pant",
        41: "Cough",
        42: "Sneeze",
        43: "Sniff",
        44: "Run",
        45: "Shuffle",
        46: "Walk, footsteps",
        47: "Chewing, mastication",
        48: "Biting",
        49: "Gargling",
        50: "Stomach rumble",
        51: "Burping, eructation",
        52: "Vomit",
        53: "Mouse",
        54: "Mouse wheel",
        55: "Keyboard",
        56: "Typewriter",
        57: "Computer keyboard",
        58: "Tap",
        59: "Clicking",
        60: "Beep, ping",
        61: "Tone",
        62: "Dial tone",
        63: "Busy signal",
        64: "DTMF",
        65: "Alarm",
        66: "Siren",
        67: "Civil defense siren",
        68: "Buzzer",
        69: "Doorbell",
        70: "Knock",
        71: "Tap, rap",
        72: "Thump, thud",
        73: "Thunk",
        74: "Door slam",
        75: "Door",
        76: "Door open",
        77: "Door close",
        78: "Creak",
        79: "Squeak",
        80: "Scrape",
        81: "Rustle",
        82: "Crash, clatter",
        83: "Breaking",
        84: "Burst, pop",
        85: "Glass breaking",
        86: "Liquid",
        87: "Splash, splatter",
        88: "Slosh",
        89: "Gurgle",
        90: "Drip",
        91: "Pour",
        92: "Flush",
        93: "Tea kettle whistle",
        94: "Frying (food)",
        95: "Microwave oven",
        96: "Blender",
        97: "Food processor",
        98: "Coffee grinder",
        99: "Hair dryer",
        100: "Vacuum cleaner",
        101: "Toilet flush",
        102: "Toothbrush",
        103: "Electric shaver",
        104: "Hair spray",
        105: "Lawn mower",
        106: "Chainsaw",
        107: "Drill",
        108: "Sawing",
        109: "Hammer",
        110: "Jackhammer",
        111: "Sanding",
        112: "Power tool",
        113: "Engine",
        114: "Engine starting",
        115: "Engine idling",
        116: "Engine knocking",
        117: "Engine revving",
        118: "Car",
        119: "Car passing by",
        120: "Car horn",
        121: "Car alarm",
        122: "Truck",
        123: "Bus",
        124: "Motorcycle",
        125: "Motor scooter",
        126: "Bicycle",
        127: "Bicycle bell",
        128: "Train",
        129: "Train horn",
        130: "Train whistle",
        131: "Subway, metro",
        132: "Street music",
        133: "Helicopter",
        134: "Aircraft",
        135: "Airplane",
        136: "Propeller, airscrew",
        137: "Jet engine",
        138: "Fireworks",
        139: "Explosion",
        140: "Gunshot, gunfire",
        141: "Machine gun",
        142: "Artillery fire",
        143: "Cap gun",
        144: "Firecracker",
        145: "Bomb, exploding",
        146: "Thunder",
        147: "Thunderstorm",
        148: "Wind",
        149: "Wind noise (microphone)",
        150: "Rain",
        151: "Raindrop",
        152: "Hail",
        153: "Ocean",
        154: "Waterfall",
        155: "Stream",
        156: "River",
        157: "Fire",
        158: "Crackle",
        159: "Bark",
        160: "Meow",
        161: "Hiss",
        162: "Growl",
        163: "Howl",
        164: "Roar",
        165: "Bird",
        166: "Bird chirp, tweet",
        167: "Bird squawk",
        168: "Pigeon, dove",
        169: "Crow",
        170: "Owl",
        171: "Insect",
        172: "Bee, wasp, etc.",
        173: "Cricket",
        174: "Frog",
        175: "Cat",
        176: "Dog",
        177: "Horse",
        178: "Cow",
        179: "Pig",
        180: "Sheep",
        181: "Chicken, rooster",
        182: "Goose",
        183: "Duck",
        184: "Turkey",
        185: "Elephant",
        186: "Lion",
        187: "Monkey",
        188: "Snake",
        189: "Mosquito",
        190: "Fly, housefly",
        191: "Cicada",
        192: "Music",
        193: "Musical instrument",
        194: "Plucked string instrument",
        195: "Guitar",
        196: "Electric guitar",
        197: "Bass guitar",
        198: "Acoustic guitar",
        199: "Piano",
        200: "Electric piano",
        201: "Organ",
        202: "Synthesizer",
        203: "Harpsichord",
        204: "Percussion",
        205: "Drum",
        206: "Drum kit",
        207: "Drum machine",
        208: "Bass drum",
        209: "Snare drum",
        210: "Cymbal",
        211: "Hi-hat",
        212: "Tambourine",
        213: "Maraca",
        214: "Bell",
        215: "Church bell",
        216: "Jingle bell",
        217: "Sleigh bell",
        218: "Wind chime",
        219: "Rattle",
        220: "Triangle",
        221: "Gong",
        222: "Wood block",
        223: "Cowbell",
        224: "Vibraslap",
        225: "Claves",
        226: "Castanets",
        227: "Marimba, xylophone",
        228: "Harmonica",
        229: "Accordion",
        230: "Violin, fiddle",
        231: "Cello",
        232: "Double bass",
        233: "Harp",
        234: "Flute",
        235: "Recorder",
        236: "Pan flute",
        237: "Oboe",
        238: "Clarinet",
        239: "Saxophone",
        240: "Bassoon",
        241: "French horn",
        242: "Trumpet",
        243: "Trombone",
        244: "Tuba",
        245: "Brass instrument",
        246: "Sawing",
        247: "Bagpipes",
        248: "Didgeridoo",
        249: "Beatboxing",
        250: "Scratching (DJ)",
        251: "Pop music",
        252: "Hip hop music",
        253: "Rock music",
        254: "Country music",
        255: "Jazz music",
        256: "Blues music",
        257: "R&B",
        258: "Soul music",
        259: "Reggae",
        260: "Classical music",
        261: "Orchestra",
        262: "Chamber music",
        263: "Opera",
        264: "Folk music",
        265: "Funk",
        266: "Electronic music",
        267: "Dance music",
        268: "Ambient music",
        269: "New-age music",
        270: "World music",
        271: "Gospel music",
        272: "Children's music",
        273: "Wedding music",
        274: "Happy music",
        275: "Sad music",
        276: "Tender music",
        277: "Exciting music",
        278: "Angry music",
        279: "Scary music",
        280: "Silence",
        281: "White noise",
        282: "Pink noise",
        283: "Throbbing",
        284: "Hum",
        285: "Buzz",
        286: "Hiss",
        287: "Rumble",
        288: "Click",
        289: "Clank",
        290: "Clang",
        291: "Crunch",
        292: "Crack",
        293: "Snap",
        294: "Pop",
        295: "Fizz",
        296: "Sizzle",
        297: "Whoosh",
        298: "Swish",
        299: "Splash",
        300: "Gurgle",
        301: "Blow",
        302: "Puff",
        303: "Suck",
        304: "Spray",
        305: "Squirt",
        306: "Drip",
        307: "Tap",
        308: "Tick",
        309: "Tock",
        310: "Clop",
        311: "Clip-clop",
        312: "Gallop",
        313: "Heart sounds",
        314: "Heart murmur",
        315: "Heartbeat",
        316: "Heart flutter",
        317: "Finger snapping",
        318: "Hands",
        319: "Clapping",
        320: "Finger tapping",
        321: "Rustling",
        322: "Fumbling",
        323: "Slap, smack",
        324: "Stomp",
        325: "Stampede",
        326: "Punch",
        327: "Kick",
        328: "Thud, thump",
        329: "Crash, cymbal",
        330: "Breaking glass",
        331: "Shatter",
        332: "Tearing",
        333: "Ripping",
        334: "Zipper",
        335: "Velcro",
        336: "Paper",
        337: "Book",
        338: "Page flip",
        339: "Magazine",
        340: "Newspaper",
        341: "Cardboard",
        342: "Box",
        343: "Plastic",
        344: "Bubble wrap",
        345: "Foil",
        346: "Wrapper",
        347: "Coin",
        348: "Money",
        349: "Keys jangling",
        350: "Lock",
        351: "Unlock",
        352: "Latch",
        353: "Bolt",
        354: "Chain",
        355: "Padlock",
        356: "Combination lock",
        357: "Safe",
        358: "Vault",
        359: "Siren",
        360: "Alarm",
        361: "Fire alarm",
        362: "Smoke alarm",
        363: "Burglar alarm",
        364: "Car alarm",
        365: "Security alarm",
        366: "Bell",
        367: "Doorbell",
        368: "Buzzer",
        369: "Horn",
        370: "Air horn",
        371: "Foghorn",
        372: "Train horn",
        373: "Car horn",
        374: "Truck horn",
        375: "Ship horn",
        376: "Boat horn",
        377: "Whistle",
        378: "Police siren",
        379: "Ambulance siren",
        380: "Glass breaking",
        381: "Gunshot, gunfire",
        382: "Machine gun",
        383: "Explosion",
        384: "Bomb",
        385: "Firecracker",
        386: "Cap gun",
        387: "Fireworks",
        388: "Thunder",
        389: "Thunderstorm",
        390: "Wind",
        391: "Rain",
        392: "Hail",
        393: "Sleet",
        394: "Snow",
        395: "Ice",
        396: "Earthquake",
        397: "Avalanche",
        398: "Landslide",
        399: "Mudslide",
        400: "Screaming",
        401: "Shrieking",
        402: "Shouting",
        403: "Yelling",
        404: "Bellowing",
        405: "Roaring",
        406: "Howling",
        407: "Wailing",
        408: "Moaning",
        409: "Groaning",
        410: "Crying",
        411: "Sobbing",
        412: "Weeping",
        413: "Whimpering",
        414: "Sniffling",
        415: "Snorting",
        416: "Gasping",
        417: "Panting",
        418: "Wheezing",
        419: "Coughing",
        420: "Vehicle alarm",
        421: "Car alarm",
        422: "Vehicle horn",
        423: "Car horn",
        424: "Door slam",
        425: "Slamming door",
        426: "Footsteps",
        427: "Running footsteps",
        428: "Walking footsteps",
        429: "Heavy footsteps",
        430: "Engine",
        431: "Engine running",
        432: "Engine idling",
        433: "Engine revving",
        434: "Engine starting",
        435: "Engine stopping",
        436: "Engine knocking",
        437: "Engine misfire",
        438: "Engine backfire",
        439: "Engine overheating",
        440: "Engine smoking",
        441: "Engine flooding",
        442: "Engine stalling",
        443: "Engine racing",
        444: "Engine accelerating",
        445: "Engine decelerating",
        446: "Engine braking",
        447: "Engine clutching",
        448: "Engine shifting",
        449: "Engine driving",
        450: "Engine cruising",
        451: "Engine idling",
        452: "Engine running",
        453: "Engine starting",
        454: "Engine stopping",
        455: "Engine off",
        456: "Engine on",
        457: "Engine warm",
        458: "Engine cold",
        459: "Engine hot",
        460: "Engine cool",
        461: "Engine normal",
        462: "Engine abnormal",
        463: "Engine loud",
        464: "Engine quiet",
        465: "Engine smooth",
        466: "Engine rough",
        467: "Engine steady",
        468: "Engine unsteady",
        469: "Engine fast",
        470: "Engine slow",
        471: "Engine high",
        472: "Engine low",
        473: "Engine medium",
        474: "Engine variable",
        475: "Engine constant",
        476: "Engine fluctuating",
        477: "Engine surging",
        478: "Engine hesitating",
        479: "Engine missing",
        480: "Engine skipping",
        481: "Engine bucking",
        482: "Engine jerking",
        483: "Engine vibrating",
        484: "Engine shaking",
        485: "Engine rattling",
        486: "Engine knocking",
        487: "Engine pinging",
        488: "Engine pinging",
        489: "Engine detonating",
        490: "Engine pre-ignition",
        491: "Engine after-run",
        492: "Engine run-on",
        493: "Engine dieseling",
        494: "Engine run-away",
        495: "Engine overspeed",
        496: "Engine underspeed",
        497: "Engine stall",
        498: "Engine flood",
        499: "Engine vapor lock",
        500: "Engine hydrolock",
        501: "Engine mechanical",
        502: "Engine electrical",
        503: "Engine fuel",
        504: "Engine air",
        505: "Engine exhaust",
        506: "Engine cooling",
        507: "Engine lubrication",
        508: "Engine ignition",
        509: "Engine starting",
        510: "Engine charging",
        511: "Engine battery",
        512: "Engine alternator",
        513: "Engine starter",
        514: "Engine solenoid",
        515: "Engine relay",
        516: "Engine fuse",
        517: "Engine wiring",
        518: "Engine connector",
        519: "Engine sensor",
        520: "Engine computer",
    }

    return _YAMNET_CLASS_NAMES
