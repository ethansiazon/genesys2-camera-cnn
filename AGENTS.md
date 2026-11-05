# Camera/CNN project rules

Read README.md and docs/CURRENT_STATUS.md first. Historical handoff notes are
evidence, not authorization to run jobs, install software, or program hardware.

- Keep camera/versions immutable; camera/working is the camera editing location.
- Preserve retained CNN weights, data splits, exact preprocessing and test vectors.
- Make local commits at meaningful checkpoints. Ask Ethan before every push,
  including first publication, release upload, or remote branch creation.
- Pull/check the remote before starting a new shared task. Never force-push,
  overwrite teammates' work, or change repository access without authorization.
- Preserve GPL/vendor licenses and provenance. Never commit secrets, datasets,
  user documents, USB driver packages or unrelated project subsystems.
- One heavy compiler/training job at a time; maintain the 1.5 GiB memory guard.
  Do not close unrelated apps or change Windows settings.
- Verify current wiring and switches before board programming. No QSPI/SD writes,
  driver repair, board programming or actuator/aiming work without explicit scope.
- Preserve short-pulse rejection. Change one camera variable at a time; record
  source/bit hashes, settings, raw data and user observations. Clean bars alone
  do not prove correct live colour. Run checks appropriate to any change.
- Do not claim full-system fit/FPS or accuracy from tiny simulations, OOC results,
  selected positive samples, or assumed software scheduling.
