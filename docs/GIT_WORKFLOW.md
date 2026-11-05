# Saving and sharing work

- **Commit:** a named checkpoint saved on this laptop.
- **Push:** upload those commits to GitHub so teammates can get them.
- **Pull:** get the latest shared work before editing.
- **Branch:** a separate experiment, so the baseline remains recoverable.

Baseline import is on main, with a baseline tag. Camera debugging starts on
camera/color-debug. Future improvements should use small commits with actual
test results. Push after a reproducible fix, a documented failed experiment worth
sharing, or a handoff; avoid uploading every tiny edit.

Before each push, the assistant tells Ethan what changed, what passed, what is
still broken, and which files/branch will be uploaded. Ethan approves the push.
Approval applies to that push only. No automatic pushes or releases.

Teammates should use their own branches and review changes before merging into
main. Do not edit the same files simultaneously without coordination. Never
force-push shared branches. The GitHub repository is private; collaborators must
be explicitly invited by Ethan. No invitation is sent automatically.
