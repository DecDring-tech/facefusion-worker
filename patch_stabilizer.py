"""
TEMPORAL LANDMARK STABILIZER — patches FaceFusion's face_swapper at Docker-build time.

WHY: FaceFusion warps the swapped face from PER-FRAME 5-point landmarks with zero temporal
smoothing. When a hand/product partially covers the face (constant in GRWM footage), those
landmarks oscillate frame-to-frame → the warp matrix shakes → the face looks "wobbly like
jelly". No CLI flag fixes this; it must be patched into the source.

WHAT: an exponential-moving-average over the target face's 5-point landmarks, with a
jump-reset (a real head move / hard cut resets the state instead of smearing). Valid only
when frames are processed IN ORDER — the handler runs with --execution-thread-count 1.

Applied against the PINNED FaceFusion version in the Dockerfile. If an anchor string is not
found (version drift), this script EXITS NON-ZERO and fails the build loudly — never silently
skips.
"""

import sys

CORE = "/app/facefusion/facefusion/processors/modules/face_swapper/core.py" if len(sys.argv) < 2 else sys.argv[1]

STABILIZER = '''
# ── TEMPORAL LANDMARK STABILIZER (adspark patch) ────────────────────────────────────────────────
# EMA over the target 5-point landmarks so partial-occlusion jitter can't shake the swap warp.
# Requires sequential frame processing (--execution-thread-count 1). Resets on a real jump
# (> half the inter-eye distance) so head motion and hard cuts stay crisp.
FACE_STABILIZER_STATE = { 'landmark_5' : None }


def stabilize_face_landmark_5(face_landmark_5):
	previous = FACE_STABILIZER_STATE.get('landmark_5')
	if face_landmark_5 is None:
		return face_landmark_5
	if previous is not None and previous.shape == face_landmark_5.shape:
		center_delta = float(numpy.linalg.norm(numpy.mean(face_landmark_5, axis = 0) - numpy.mean(previous, axis = 0)))
		eye_distance = float(numpy.linalg.norm(face_landmark_5[0] - face_landmark_5[1])) + 1e-6
		if center_delta < eye_distance * 0.5:
			face_landmark_5 = previous * 0.6 + face_landmark_5 * 0.4
	FACE_STABILIZER_STATE['landmark_5'] = face_landmark_5
	return face_landmark_5
'''

ANCHOR_DEF = "def swap_face(source_face : Face, target_face : Face, source_vision_frame : VisionFrame, temp_vision_frame : VisionFrame) -> VisionFrame:"
ANCHOR_WARP = "crop_vision_frame, affine_matrix = warp_face_by_face_landmark_5(temp_vision_frame, target_face.landmark_set.get('5/68'), model_template, pixel_boost_size)"
PATCHED_WARP = "crop_vision_frame, affine_matrix = warp_face_by_face_landmark_5(temp_vision_frame, stabilize_face_landmark_5(target_face.landmark_set.get('5/68')), model_template, pixel_boost_size)"

with open(CORE, "r", encoding="utf-8") as f:
    src = f.read()

if "stabilize_face_landmark_5" in src:
    print("patch_stabilizer: already applied")
    sys.exit(0)
if ANCHOR_DEF not in src or ANCHOR_WARP not in src:
    print("patch_stabilizer: ANCHOR NOT FOUND — FaceFusion source changed; refusing to build unpatched", file=sys.stderr)
    sys.exit(1)

# Insert the stabilizer right above swap_face, and route the TARGET warp (only) through it.
src = src.replace(ANCHOR_DEF, STABILIZER + "\n\n" + ANCHOR_DEF, 1)
src = src.replace(ANCHOR_WARP, PATCHED_WARP, 1)

with open(CORE, "w", encoding="utf-8") as f:
    f.write(src)
print("patch_stabilizer: applied OK")
