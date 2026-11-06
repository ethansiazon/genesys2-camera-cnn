# Genesys 2 camera and CNN

Source control for Ethan's OV5640 camera work, the retained V5 epoch-8/R9
drone detector, and Niko's October 29 FPGA implementation. These are separate
working subsystems. The live camera has not yet been connected to the CNN.

## Start here

| Folder | Purpose |
|---|---|
| `camera/working/` | Editable copy of the preferred final manual-exposure receiver; start debugging here. |
| `camera/versions/` | Preserved best receiver, final exposure trial, and raw recorder. |
| `cnn/` | Retained software, two trusted checkpoints, HLS, generated RTL, tests and provenance. |
| `fpga_system/` | Niko's DDR3/CNN/decoder integration and October 29 board results. |
| `docs/CURRENT_STATUS.md` | Current results, limits, and next debugging steps. |
| `docs/GIT_WORKFLOW.md` | Short instructions for saving and sharing changes. |

Original handoff files have been preserved. Some original READMEs describe old
states and absolute paths. Read CURRENT_STATUS before acting on historical notes.
The original folders on the Desktop were not changed.

## Camera baseline

**Active baseline, selected 4 November:** `camera/versions/last_exposure_test`.
`camera/working` now copies this preferred final exposure version. The older
`best_receiver` name describes a historical receiver checkpoint, not the user's
current preferred picture. See `docs/CAMERA_PREFERRED_BASELINE_20261104.json`.

The best receiver produced clean camera-generated bars and clear live video.
Bright/white regions still had incorrect green/purple colours. The last separate
manual-exposure trial reduced those symptoms but made the picture too dark.

Camera capture: 320 x 240 YUV422, converted to RGB. HDMI: 640 x 480 at 60 Hz,
25.2 MHz pixel clock and 126 MHz serializer clock. Only SW6 up + BTNC selects
normal live viewing. PCLK is JA physical 1; D6 is JB physical 8. Check the full
`camera/WIRING.md` against actual wiring before programming.

To create a new editable project from `camera/working`, in Vivado Tcl:

```tcl
cd C:/Users/ethan/Desktop/genesys2-camera-cnn
set argv [list C:/g2_camera_work_02]
source tools/create_camera_project.tcl
```

The script creates a project only. Use a fresh output directory and keep builds
outside tracked sources. Original camera tools: Vivado 2026.1. Niko's FPGA system
was generated and implemented with Vivado/Vitis HLS 2023.2 on Linux; these are
different tool baselines and are not interchangeable guarantees.

Offline receiver checks (no board access):

```powershell
python tools/test_camera.py --out local_results/camera_baseline_01
```

For software model setup see `cnn/software/README.md`. Retained weights are
`cnn/weights/epoch_08.pt` and `cnn/weights/quantized_fx.pt`. Bulk datasets are
not included. Do not load untrusted checkpoints.

## What belongs in Git

Sources, constraints, scripts, weights, compact test vectors and reports are
tracked. Vivado build folders, bitstreams, routed checkpoints, videos, photos,
raw camera captures and environments are ignored. Copies of the original
artifacts remain locally in this tree and in the untouched handoffs; they are
not promised to exist after a fresh Git clone. Share selected tested bitstreams
through a release/archive after approval, with their matching commit and hash.
Do not interpret a missing ignored artifact as a missing source file.

Third-party licenses and attribution stay with the supplied code. This is a
private project repository; no new blanket license is granted to vendor files,
datasets, or teammate contributions. See `docs/THIRD_PARTY.md`.
