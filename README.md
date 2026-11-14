# shot-renamer

Renames film takes from the slate spoken at the head of the file. It pulls the
first 15 seconds of audio with `ffmpeg`, transcribes it with Whisper, finds
`Scene X, Shot Y, Take Z`, and renames the file to `SceneXX ShotYY TakeZZ`.

```
A045_01261916_C065.mov   ->   Scene04 Shot02 Take03.mov
```

## Install

Requires `ffmpeg` on `PATH` (probe and audio extraction) and Python 3.10+.

```sh
python3 -m venv .venv
.venv/bin/pip install -e .
```

The first transcription downloads the Whisper model (~460 MB for `small.en`)
into `~/.cache/huggingface`.

## Install on macOS

Runs on Apple Silicon and Intel with macOS 11+ (Sonoma or newer resolves the
newest wheels). There is no GPU path — CUDA does not exist on macOS, so it
transcribes on CPU: a few seconds per take. Neither `ffmpeg` nor a suitable
Python ships with macOS, so both need installing first.

### 1. Check the basics

```sh
uname -m                  # arm64 = Apple Silicon, x86_64 = Intel
sw_vers -productVersion
python3 --version         # macOS's built-in python3 is 3.9 — too old
ffmpeg -version
```

You need **Python 3.10 or newer** and **ffmpeg**.

### 2. Install ffmpeg and Python

**With Homebrew** (easiest; Homebrew itself asks for an admin password once):

```sh
brew install ffmpeg python@3.12
```

On Apple Silicon, make sure Homebrew is on `PATH` in new shells:

```sh
echo 'eval "$(brew shellenv)"' >> ~/.zprofile
```

**Without admin rights** — micromamba keeps Python and ffmpeg entirely in your
home directory:

```sh
curl -Ls https://micro.mamba.pm/api/micromamba/osx-arm64/latest | tar -xvj bin/micromamba
./bin/micromamba create -y -p ~/slate -c conda-forge python=3.12 ffmpeg
```

Use `osx-64` instead of `osx-arm64` on an Intel Mac. Then substitute
`~/slate/bin/python` and `~/slate/bin/shot-renamer` for the paths below. (The
official python.org installer works too, but ffmpeg still needs a separate
download.)

### 3. Install shot-renamer

```sh
git clone https://github.com/<your-user>/shot-renamer.git
cd shot-renamer
python3.12 -m venv .venv
.venv/bin/pip install -e .
```

The CLI lands at `.venv/bin/shot-renamer`. Run `source .venv/bin/activate` if
you would rather type the bare command.

### 4. Fetch the model once

The first transcription downloads `small.en` (~460 MB) into
`~/.cache/huggingface`. If the campus network blocks HuggingFace, copy that
directory from a machine that already has it and the tool runs offline:

```sh
rsync -a other-machine:~/.cache/huggingface/ ~/.cache/huggingface/
```

### 5. First run

```sh
.venv/bin/shot-renamer ~/Movies/takes --show-transcript   # dry run
.venv/bin/shot-renamer ~/Movies/takes --apply             # commit
```

macOS will ask for permission the first time Terminal reads Desktop,
Documents, Downloads or an external drive. Allow it, or the tool sees an empty
folder.

### Troubleshooting

| Symptom | Fix |
|---|---|
| `ffmpeg: command not found` | Homebrew is not on `PATH` — add `eval "$(brew shellenv)"` to `~/.zprofile` and open a new terminal |
| `bad CPU type in executable` | Intel Homebrew in `/usr/local` mixed with an arm64 Python; install both for the same architecture |
| `No module named pip` | `.venv/bin/python -m ensurepip --upgrade` |
| `command not found: shot-renamer` | Use `.venv/bin/shot-renamer`, or activate the venv first |
| Model download hangs | Use the cache copy above; the tool then runs offline |
| Empty file list or `Permission denied` | System Settings → Privacy & Security → Files and Folders: grant Terminal access |
| `operation not permitted` on a hand-downloaded ffmpeg | `xattr -d com.apple.quarantine /path/to/ffmpeg` |

## Use

```sh
shot-renamer footage/                 # dry run, shows what would happen
shot-renamer footage/ --apply         # do it
shot-renamer clip.mov clip2.mov -r    # explicit files, or recurse
```

It is a **dry run unless you pass `--apply`**. Nothing is ever overwritten: a
target that already exists is stepped over with a `_2`, `_3`, … suffix, and
same-slate files (A-cam/B-cam of one take) are suffixed in filename order.

Files that already carry a correctly formatted name are left alone, so re-runs
are harmless.

### Options

| Flag | Meaning |
|---|---|
| `--apply` | rename for real (default: dry run) |
| `-r`, `--recursive` | descend into directories |
| `--seconds N` | audio window to transcribe (default 15) |
| `--model small.en` | Whisper model; try `medium.en` for noisy sets |
| `--device auto\|cpu\|cuda` | `auto` uses CUDA when it actually works |
| `--compute-type` | ctranslate2 precision, `auto` = float16 on GPU, int8 on CPU |
| `--show-transcript` | print what Whisper heard — first thing to check on a miss |
| `--log FILE` | CSV audit log (always written with `--apply`) |
| `--json` | machine-readable output |
| `-q`, `--quiet` | summary only |

Exit codes: `0` everything resolved, `1` at least one file had no usable slate
or failed, `2` bad invocation.

## Naming

| Heard | Renamed to |
|---|---|
| Scene 12, Shot 3, Take 2 | `Scene12 Shot03 Take02.mov` |
| Scene 12A, Shot 3, Take 2 | `Scene12A Shot03 Take02.mov` |
| Scene 7, Shot 12, Take 10 | `Scene07 Shot12 Take10.mov` |
| Scene 100, Shot 3, Take 2 | `Scene100 Shot03 Take02.mov` |

Scene and shot pad to two digits, take to two, and three-digit numbers are left
unpadded. Scene suffixes keep the letter. The original extension is preserved.

## How a slate is found

`slate.parse` works on text only, which is why it is tested without a model. It
copes with the way people actually say slates and the way ASR mangles them:

- numbers as digits, words (`twelve`), or digit-by-digit (`scene one two`)
- lowercase/uppercase, stray punctuation, `scene12`
- phonetic scene letters (`scene twelve apple` → `12A`)
- near-miss keywords (`seen`, `shots`)
- filler words between labels (`scene twelve, and shot three, take two`)

A slate must be complete and plausible (scene/shot 1–999, take 1–99). Anything
else is reported as `no-slate` and left untouched. Silent audio is rejected
before parsing so a prompt-biased model cannot invent a slate from room tone.

Every file gets a status: `renamed`/`would-rename`, `already-named`, `no-slate`,
`no-audio`, `not-media` (not decodable — skipped in directory scans) or `error`
(a file you named directly that could not be read).

## Why faster-whisper

It runs on CPU and CUDA without PyTorch, loads once per batch, and accepts raw
samples, so nothing is written to disk. `--device auto` probes for CUDA and
falls back to CPU with a warning if the system CUDA libraries are missing.

## Development

```sh
.venv/bin/python -m pytest
```

Parser, naming and collision rules are pure functions; media tests exercise
real `ffmpeg` against generated tones.

## License

MIT — see [LICENSE](LICENSE).
