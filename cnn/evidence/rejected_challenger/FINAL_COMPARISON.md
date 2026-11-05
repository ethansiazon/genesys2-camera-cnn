# Focused training result — keep the current model

Two fine-tuning epochs and one paired normalization check are complete. Neither new trained copy improved on the current model under the same float evaluation. The early-stop rule ended training after two epochs. No extra quantization or FPGA compiler run was spent on a worse candidate.

| Matched evaluation | Correct-box recall | F1 | Empty frames with a trigger |
|---|---:|---:|---:|
| Current model, float reference | 79.24% | 80.50% | 6 / 328 |
| New fine-tune epoch 1 | 78.46% | 79.77% | 16 / 328 |
| New fine-tune epoch 2 | 76.23% | 78.12% | 0 / 328 |
| Epoch 1 with original normalization statistics | 76.37% | 78.12% | 0 / 328 |

These are matched float-CNN evaluations using the same integer decoder and R9 tracking policy. The retained deployed-format R9 result remains79.96%correct-boxrecall/81.37%F1; do not mix its fixed-point figures into the float experiment comparison. All46nativeVALclips/17193frames were checked in every evaluation.

Bird/plane/helicopter rejection was not a promotion requirement. The new candidates failed because drone-box performance fell. Their strict other-aircraft metrics remain separate.

Training focused85%on original sampling,10%on selected difficult positives and5%on reviewed difficult empty backgrounds. The150extra views came from existing TRAIN source frames; they add practice rather than new independent scene diversity. A visible drone-shaped object in one absent-labelled TRAIN frame was excluded from this new trial only; originals remain untouched.

The normalization diagnostic kept all epoch1 learned weights and restored only the original TRAIN-derived running normalization buffers. It removed author-empty triggers in this sample but lowered drone recall, so it did not resolve the regression. No new architecture or layers were added.

**Decision: retain the original V5 epoch8 + R9 settings.** Original model, quantized coefficients, routed core, preferred configuration, data and splits are unchanged. Both new trained checkpoints and full-frame results are saved. This unsuccessful recipe does not prove the architecture cannot improve; more independent, reliably labelled target-environment examples are a more useful next data direction than blindly repeating this weighting or extending these epochs. Actual new training is stopped.

Evidence: [VERIFIED_FINAL.json](VERIFIED_FINAL.json), [TRAINING_PLAN.md](TRAINING_PLAN.md), [epoch1 review](epoch_01_GATE.json), [epoch2 review](epoch_02_GATE.json), [normalization review](bn_reference_diagnostic_r11/REVIEW.json).
