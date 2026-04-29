import os
import time
import json
from datetime import datetime
import numpy as np
from PIL import Image
import mss


# ------- CONFIG (tune these values) -------
FPS = 1
INTERVAL = 1.0 / FPS
MEAN_DIFF_THRESHOLD = 30.0          # mean gray diff threshold (tune)
CHANGED_PIXELS_RATIO_THRESH = 0.01  # fraction of pixels changed (tune)
PIXEL_CHANGE_VALUE = 20             # per-pixel diff to count as changed
JPEG_QUALITY = 30                   # 1-100 (lower = smaller files)

# Paths (script assumes it lives in Monitoring/)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCREEN_DIR = os.path.join(BASE_DIR, 'screenshots')
LOG_TXT = os.path.join(BASE_DIR, 'log.txt')    # your existing text log (may be named log.txt)
LOG_JSON = os.path.join(BASE_DIR, 'log.json')  # your existing json log
os.makedirs(SCREEN_DIR, exist_ok=True)

# persist last saved frame hash between runs (optional)
LAST_GRAY_PATH = os.path.join(BASE_DIR, '.last_saved_gray.npy')


def capture_fullscreen_image():
    with mss.mss() as sct:
        monitor = sct.monitors[0]
        sct_img = sct.grab(monitor)
        img = Image.frombytes('RGB', sct_img.size, sct_img.rgb)
        return img


def to_gray_np(img):
    return np.array(img.convert('L'))


# load previous saved gray if exists
prev_saved_gray = None
try:
    if os.path.exists(LAST_GRAY_PATH):
        prev_saved_gray = np.load(LAST_GRAY_PATH)
except Exception:
    prev_saved_gray = None

seq = 0
print('Recorder starting: capture 1fps, delta detection active. Ctrl+C to stop.')
try:
    while True:
        loop_start = time.time()
        img = capture_fullscreen_image()
        gray = to_gray_np(img)
        save = False
        reason = ''

        if prev_saved_gray is None:
            save = True
            reason = 'first_frame'
        else:
            # compute abs difference
            diff = np.abs(gray.astype(np.int16) - prev_saved_gray.astype(np.int16))
            mean_diff = float(diff.mean())
            changed_pixels = int((diff > PIXEL_CHANGE_VALUE).sum())
            changed_ratio = changed_pixels / diff.size

            if (mean_diff >= MEAN_DIFF_THRESHOLD) and (changed_ratio >= CHANGED_PIXELS_RATIO_THRESH):
                save = True
                reason = 'delta_pass'
            else:
                save = False
                reason = 'no_significant_change'

        if save:
            seq += 1
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'screenshot_{ts}_{seq:03d}.jpg'
            tmp_path = os.path.join(SCREEN_DIR, filename + '.tmp')
            final_path = os.path.join(SCREEN_DIR, filename)

            # save compressed jpg atomically
            try:
                img.save(tmp_path, 'JPEG', quality=JPEG_QUALITY, optimize=True)
                os.replace(tmp_path, final_path)
            except Exception as e:
                print('Error saving image:', e)
                if os.path.exists(tmp_path):
                    try: os.remove(tmp_path)
                    except: pass

            # append to text log
            log_line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] | Screenshot: '{os.path.join('screenshots', filename)}' | Reason: {reason}\n"
            try:
                with open(LOG_TXT, 'a', encoding='utf-8') as f:
                    f.write(log_line)
            except Exception as e:
                print('Failed to append to text log:', e)

            # append to json log (one-line JSON per record)
            try:
                entry = {
                    'timestamp': datetime.now().isoformat(),
                    'screenshot': os.path.join('screenshots', filename),
                    'reason': reason
                }
                with open(LOG_JSON, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(entry) + '\n')
            except Exception as e:
                print('Failed to append to json log:', e)

            # persist the gray frame for next run
            try:
                np.save(LAST_GRAY_PATH, gray)
                prev_saved_gray = gray
            except Exception:
                pass

        # maintain 1fps
        elapsed = time.time() - loop_start
        to_sleep = max(0, (1.0 / FPS) - elapsed)
        time.sleep(to_sleep)

except KeyboardInterrupt:
    print('\nRecorder stopped by user.')

