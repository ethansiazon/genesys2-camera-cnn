# Third-party sources

Original licenses, credits and handoff provenance are retained in their folders.
YOLOv5 v7.0 (Ultralytics), commit 915bbf294bb74c859f0b41f1c23bc395014ea679,
is vendored with its GPL-3.0 license under cnn/software/vendor. The detector is a
custom adaptation. No license change is implied by making this private repository.
AMD/Xilinx generated RTL and memory models retain their notices and vendor terms.
Dataset images/videos are excluded from the initial tracked set; their original
attribution remains in the handoff. Weights and metadata retain their provenance.

Design background: Hobden et al., DOI 10.3389/frspt.2022.878010 (motion + CNN);
ByteTrack, arXiv:2110.06864 (low-confidence association inspiration); Zhang et al.,
DOI 10.1145/2684746.2689060 (computation reuse). These are inspiration, not exact
reproductions or evidence that this full system fits. Camera references: OV5640
product specification, Espressif esp32-camera OV5640 driver, Digilent Genesys 2
manual. See the subsystem READMEs for links and original source details.


Camera colour trials November5,2026: register recipes in
camera/working/scripts/camera_trials.json are adapted from Espressif
esp32-camera sensors/private_include/ov5640_settings.h. Project Apache2.0
license retained at docs/camera_colour_trials_20261105/ESPRESSIF_LICENSE.txt.
The inspected ov5640.c separately retains its OpenMV MIT notice; no full driver
was copied. Recipe scope/provenance and downloaded source hashes accompany
these adaptations. Original third-party notices remain intact.
