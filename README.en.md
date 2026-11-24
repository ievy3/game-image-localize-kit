# Image Text Localization Kit — Codex CLI · Claude Code

[한국어](README.md) | English

A kit for **replacing Japanese text inside game images (PNG) with Korean**. It works with any platform (PSP, 3DS, NDS, GBA, …). Getting images out of the game and back in is that platform's tooling; this kit covers everything **from the original PNG to the fixed PNG**.

- For every image, the text positions are measured into a **grid file**, and each text box is sorted into one of three classes: **clear text**, **background text** and **design text**.
- Text over a background is handed to the **Codex CLI** as a bundle: grid images plus an instruction sheet. Codex makes a first pass, then a second check pass, and the results are machine-checked.
- A person reviews a **comparison HTML** (original | result | changed pixels) and marks each image pass or fail.
- The kit uses whichever account is logged in to the CLI on this PC. It contains no accounts or keys.
- Name the kit folder and the work folders anything you like and put them anywhere.

> **Language note:** the docs, rules (`IMAGE_RULES.md`), tool messages and the instruction sheets sent to Codex are written in **Korean**, and the instructions assume **Japanese → Korean**. For another source or target language, edit the instruction text in `tools/imggrid.py` and the prompts in `tools/imgcodex.py`.

## The three classes — what is behind the text, and what kind of lettering is it
| Class | What kind of text | Erasing | Writing the new text |
|---|---|---|---|
| **Clear text** (`clear`) | Text with a transparent surround: erasing it leaves only empty space | Directly (set the text pixels' alpha to 0) | **Render it yourself** with a font |
| **Background text** (`bg`) | Text over a picture or pattern, but re-drawable with a normal font | **Codex** erases the Japanese and restores the background where it was; leftover ink is machine-measured | **Render it yourself** where the Japanese was erased, on the restored background |
| **Design text** (`design`) | Logos, handwriting, decorative or effect lettering | **Codex** | **Codex** (it delivers the finished image) |

When unsure between background text and design text, use design text. In the grid file's `분류` (class) column write `clear`, `bg`, `design` or `keep` (text to leave alone). "Yourself" means the person or agent doing the work (Claude Code, for example) draws the text with a font. This is more precise when items on the same screen, such as menu entries, must match in font, size and alignment (±2px).

## One-time setup (per PC)
1. **Python 3.9+** and the packages: `pip install pillow numpy scipy opencv-python-headless`
2. **Codex CLI** (needed for background text and design text):
   - Install Node.js, then `npm install -g @openai/codex`.
   - Run `codex login` and sign in with your own account (a ChatGPT plan or an OpenAI API account).
   - Check: `python tools/img.py login`
   - The default model is `gpt-6.2-astra` with reasoning effort high. If your plan doesn't include it, use `imgcodex --model <name>`.
3. Fonts: any SIL OFL font works. Put it in `fonts/` together with its license file. [`FONTS.md`](FONTS.md) has a recommended list.
4. (Optional) **Claude Code**, to work through the steps in chat with the `/image-localize` skill below.

## Work folder (default layout)
Create one per game, anywhere, with any name.
```
<work folder>/
  src/      original PNGs extracted from the game
  grids/    grid files BOXES_<image name>.csv
  bundles/  Codex bundles (imggrid → imgcodex)
  ko/       final PNGs that passed review (only these go back into the game)
  review/   comparison HTML and verdict CSVs
```

## Steps
Every command is `python <kit>/tools/img.py <command>` (each takes `-h`). Below it is shortened to `img.py`, run from the work folder.

1. **Find the images that contain text.** Don't only look on a white background; also check the dark-background contact sheet:
   `img.py imgdark --src src --out dark`
2. **Make the grid files.** Create `grids/BOXES_<name>.csv` for each image.
   - Columns: `file,x0,y0,x1,y1,kind,id,jp,ko,분류,grid,note`.
     - `x1`/`y1` are exclusive.
     - `kind` is `edit` or `keep`.
     - `분류` (class) is `clear`, `bg`, `design` or `keep`.
   - Measure from the original image itself, snapping boxes to an 8px grid.
   - The user approves the class table.
3. **Translation:** decide the Korean (`ko`) for every box. The user chooses first: (a) they supply a translation (the request sheet), or (b) the agent translates and the user approves.
   - `img.py imgreq --grids grids --out 번역요청.csv` writes the request sheet (`file, id, 분류, jp, 칸폭, 칸높이, 원문글자수, note, ko`: box width/height in px and the source character count help judge length).
   - Fill in `ko`, then `img.py imgreq --grids grids --apply 번역요청.csv` writes it into the grid files. `--check` lists boxes with an empty `ko`.
   - Clear and design boxes with an empty `ko` stop rendering and bundling.
4. **Clear text:** draw with the rendering library `tools/imgrender.py`.
   - Copy `examples/render_series.py` to `render/<series>.py`, adjust font, size and alignment, then run `python render/<series>.py`.
   - The library does the rest:
     - erases the Japanese text in each box, including overflowing outlines
     - draws the Korean text aligned to the original ink
     - shrinks the size or tightens the spacing if the text doesn't fit
     - saves the result to `ko/`
   - Fonts follow the original: if the original is dot (pixel) lettering, it uses a pixel font; if it is smooth (anti-aliased), a vector font at the **original text height** (`spec=('key', 'orig')`). Only when a vector font would be smeared at that height does smooth text fall back to a pixel font (the style's `pixel=`). `imgrender` measures all of this and prints its reasoning per box. Use `run_series` for a series: text that is the same size in the originals gets the same font and size in every image.
   - Claude, Codex or a person all use the same functions.
5. **Background text:** Codex erases the Japanese and restores the background underneath (it writes no Korean).
   - `img.py imggrid --spec grids --class bg --src src --out bundles/bg_01`
   - `img.py imgcodex bundles/bg_01` writes `bundles/bg_01/result/` and `codex_check.csv`. A box fails if its largest leftover ink blob is over 12 pixels.
   - Render the Korean text over the backgrounds that passed (`run(..., cls='bg', start='bundles/bg_01/result')` in the series script).
6. **Design text:** Codex delivers the finished image.
   - `img.py imggrid --spec grids --class design --src src --out bundles/design_01`
   - `img.py imgcodex bundles/design_01`
7. **Review:** build a comparison page every time images are changed or received:
   - `img.py imgview --orig src --result <result folder> --boxes grids --title "<series/round>" --out review/<title>.html`
   - Mark each image pass or fail and add notes, then press "Download verdict CSV" and save the file in `review/`.
   - Only images that passed go to `ko/`.
8. **Cell check** (if you have the game's layout file): `img.py imgcells --layout <layout> --orig <original> --result <result>`

If an image still fails after `imgcodex` has had its passes (first pass, second pass and a fix round), fix it by hand or give its bundle (`bundles/<name>.zip`, with grid images, instructions and the canonical text) to another tool.

## Tools
| Command | What it does |
|---|---|
| `imgreq` | Translation request sheet: lists the grid files' Japanese (`--out`), writes the filled-in Korean back into the grid files (`--apply`), lists boxes with an empty `ko` (`--check`) |
| `imggrid` | Canonical text (grid files) + originals → a bundle of grid images with numbered boxes, `지시사항.txt` (instructions), `정본.csv`, `상자.csv`, plus a .zip. `--class clear|bg|design` picks a class (`bg` makes a bundle that only erases the Japanese and restores the background), `--mistakes` adds "what went wrong last time" |
| `imgcodex` | Sends a bundle to Codex: a first pass that follows the instructions, a second check pass in the same session, then a machine check (result exists, same size, transparency kept, grey boxes untouched, background-text leftover ink). On failure it sends the problems back to the same session once more. If anything still fails it exits with code 2. `--check-only` checks without calling Codex |
| `imgview` | Side-by-side HTML of original (with boxes), result and changed pixels, with pass/fail, notes and a verdict CSV |
| `imgdark` | Dark-background contact sheet so white text on transparent images isn't missed |
| `imgcells` | Checks new text against the game layout's UV cells (0–1 floats) for overflow |
| `imgbox` | Map of pixels changed outside boxes, off screen, or inside keep boxes (reference only, not a pass/fail criterion) |
| `login` | Whether the Codex CLI is installed and logged in |

## The `/image-localize` skill — Claude Code and Codex
The kit includes the skill `.claude/skills/image-localize/`. When invoked, it walks through the steps above in chat:
- drafting grid files
- sorting text into classes (a person approves)
- the translation (asks first: the user's translation, or the agent's for the user to approve)
- rendering Korean for clear and background text
- building Codex bundles and sending them
- building comparison pages

How to get it:
- **Claude Code:** open `claude` in the kit folder and it's picked up without installing. Type `/image-localize`.
- **From any folder, or in Codex:** run `python install_skill.py`.
  - It copies the skill into `%USERPROFILE%\.claude\skills\` and `%USERPROFILE%\.codex\skills\`.
  - Use `--claude` or `--codex` for one side only, and `--remove` to uninstall.
  - The skill is picked up from the next new session. In Codex, just ask for image text localization.

Whichever agent you use, background text and design text are handled by `imgcodex`, which **launches the Codex CLI itself**, so the Codex CLI must always be installed and logged in. `imgcodex` checks the login first; if you aren't logged in, it points you to `codex login` and stops with exit code 3.

## Tests
`python tests/t_imggrid.py` · `t_imgreq.py` · `t_imgcodex.py` (fake Codex) · `t_imgview.py` · `t_imgcells.py` should all report a pass.

## Author & license
- Author: **NP (Noctil Patchworks)** — https://ievy3.github.io/
- MIT (`LICENSE`). Fonts, the Codex CLI and the Python packages are not included and follow their own licenses and terms.

## Notes
- The background-text leftover-ink threshold of 12 pixels is provisional, based on 5 sample images. Boxes containing patterns or frames can fail even when clean (it errs on the safe side).
- Codex output quality depends on the model and plan. Even passed results are reviewed by a person in the comparison HTML.
