# Evaluation results

Raw output of `evaluate.py`, one JSON per run. These live here rather than in
`data/` because `data/` is gitignored: it holds the Fashionpedia images, which
are not ours to redistribute, and the multi-gigabyte archives. Deleting `data/`
must not delete the numbers the thesis is written from.

Every file is the whole 1961-instance Fashionpedia validation split unless its
name says `subset300`, and carries its own settings in the top-level keys
(`model`, `aliases`, `prompt_ensemble`, `two_stage`, `remove_bg`), so a run can
always be traced back to what produced it.

| file | model | vocabulary | top-1 | what it shows |
|---|---|---|---|---|
| `baseline_vitb32_12labels.json` | ViT-B/32 | 12 labels | 49.0% | the starting point |
| `vitb32_aliases.json` | ViT-B/32 | 19 labels | 49.1% | the wider vocabulary is worth 0.1 here |
| `vitl14_aliases.json` | ViT-L/14 | 19 labels | 48.7% | 428M parameters buy nothing |
| `fashionclip_12labels.json` | FashionCLIP | 12 labels | 59.4% | the domain is worth 10.4 |
| `fashionclip_aliases_final.json` | FashionCLIP | 19 labels | **63.3%** | **the current pipeline** |
| `fashionclip_prompt_ensemble.json` | FashionCLIP | 19 labels | 58.6% | six averaged templates lose 0.8 |
| `subset300_vitb32_crop_only.json` | ViT-B/32 | 12 labels | 52.0% | control for the one below |
| `subset300_vitb32_rembg.json` | ViT-B/32 | 12 labels | 49.3% | background removal buys nothing |

The three runs used for the checkpoint comparison are `vitb32_aliases`,
`vitl14_aliases` and `fashionclip_aliases_final`: same vocabulary, same single
template, same crops, only the weights differ.

The two `subset300` files are a matched pair on the same seed, and are the only
place background removal is measured. They predate the F1 and macro columns, as
do `baseline_vitb32_12labels`, `fashionclip_12labels` and
`fashionclip_prompt_ensemble`; F1 for those is recomputable from the per-class
recall and precision they do carry.

Regenerate any of them:

```bash
python evaluate.py --model patrickjohncyh/fashion-clip --json results/fashionclip_aliases_final.json
python evaluate.py --model openai/clip-vit-large-patch14 --json results/vitl14_aliases.json
python evaluate.py --no-aliases --model openai/clip-vit-base-patch32 --json results/baseline_vitb32_12labels.json
```
