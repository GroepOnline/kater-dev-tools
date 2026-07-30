# Fleet timer: agent-taste + design-system brain eval

**Laptop ban:** do not enable this on `joep`. Company-control / kater host only (`chef-control-01` or existing kater runtime).

## What it runs

[`scripts/run-taste-brain-eval.sh`](../scripts/run-taste-brain-eval.sh):

1. `generate-taste.py --check` + `eval-score.py --gate` in kater-dev-tools
2. `ds brain eval` + `ds brain gate` in design-system (if `DESIGN_SYSTEM_DIR` set)
3. On fail: appends `kind=gate_fail` signal entries
4. Default: **no git commit**. Optional `--commit` pushes scorecards to `chore/eval-scorecards`

GitHub Actions also schedules the same gates (artefact upload, no auto-commit to main).

## Install (fleet)

```bash
# as operator on chef-control-01 (paths are examples — match your checkouts)
sudo install -d -o ubuntu -g ubuntu /var/lib/kater-dev-tools /var/lib/design-system
# clone or sync both repos into those dirs

sudo cp infra/taste-brain-eval.service infra/taste-brain-eval.timer /etc/systemd/system/
# edit Environment= paths in the service if needed
sudo systemctl daemon-reload
sudo systemctl enable --now taste-brain-eval.timer
systemctl list-timers taste-brain-eval.timer
```

Dry-run once:

```bash
sudo systemctl start taste-brain-eval.service
journalctl -u taste-brain-eval.service -n 80 --no-pager
```

Optional commit drop-in (`/etc/systemd/system/taste-brain-eval.service.d/commit.conf`):

```ini
[Service]
ExecStart=
ExecStart=/usr/bin/env bash /var/lib/kater-dev-tools/scripts/run-taste-brain-eval.sh --commit
```

## Dual scheduler contract

| Lane | When | Commit scorecard? |
|---|---|---|
| GHA `agent-taste-eval.yml` / `brain-eval.yml` | nightly + dispatch | no (artefact + issue on fail) |
| This systemd timer | nightly 04:40 UTC | only with `--commit` |
| PR CI (`validate` / `ci.yml`) | every PR | n/a (gate only) |
