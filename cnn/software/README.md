# Run the retained model on another computer

The new handoff runner uses the unchanged R9 tracker/integer decoder/observation logic and exact extracted motion/crop/fixed-point functions. It replaces historical path-specific orchestration, not the model. Original scripts are under ../reference_source/campaign/. It is a CPU reference replay, not a live camera or FPGA application.

## Setup (Windows PowerShell; no AMD tools needed)

Install Python 3.12 (original test environment 3.12.10). From this software directory:
```powershell
py -3.12 -m venv .venv
./.venv/Scripts/python.exe -m pip install torch==2.4.1 torchvision==0.19.1 --index-url https://download.pytorch.org/whl/cpu
./.venv/Scripts/python.exe -m pip install -r requirements.txt
./.venv/Scripts/python.exe inspect_model.py --report ../my_checks/model.json
./.venv/Scripts/python.exe run_video.py --input ../examples/smoke_input.mp4 --output ../my_checks/smoke.mp4
```

Then give run_video.py a real source clip using --input and a new --output .mp4 name. Optional --max-frames 100 limits a quick check. Use original camera footage, not a previously annotated detector output. The included smoke clip is one complete 469-frame previously used demonstration for functional testing, not a representative accuracy test. Source provenance is saved beside it.

Only load trusted .pt files: these exact files are hash-checked, but PyTorch serialization can execute Python when loading. Do not replace them with unknown downloads. No automatic network download is needed after dependency installation. Package imports disable YOLOv5 auto-install. Do not install the latest ultralytics package in place of the bundled v7 source.

Output is an annotated video at the original playback FPS, per-frame JSONL box/centre/confidence records, and a summary. It can take longer than the clip duration to compute. Video playback speed is NOT actual processing speed. Prediction frames are NOT correct detections unless independently compared to labels. The reference guards 1.5 GiB free memory and limits Torch to two CPU threads. It does not access USB, Vivado or actuators.

## Reproduce before changing

weights/epoch_08.pt contains EMA/model state, optimizer and RNG recovery from the original run. make() in model_p2_two_class.py constructs architecture; load EMA explicitly, as inspect_model.py does. A factory-created model alone is not trained. Raw FX heads are in P2 then P3 order; box decoding and tracking are separate. RGB/BGR order, 114 padding, resize interpolation, /255 normalization, trained anchors and ROI-to-frame coordinate mapping all matter.

The runner preserves the existing native-time schedule and assumed 90 ms result availability. The prior source advances at most once per video frame; do not interpret its behaviour on very low-FPS or extreme-aspect clips as a new validated operating condition. Decoder output coordinates use a 640-pixel-wide working frame and are rescaled back to native pixels for drawing.

Compatibility was checked in the existing Python 3.12/Torch 2.4.1 CPU environment, including weight load, tensor shapes and a short real-video replay. A clean installation on the teammate's actual machine still needs its own smoke test. requirements.txt gives supporting dependencies; the source environment version list is captured in package checks. Historical results are not automatically recomputed by these commands.
