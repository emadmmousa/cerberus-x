# Firebreak Hugging Face publish checklist

Authorized lab / inventory / community CC-BY data only.  
**No** scraped criminal exploit PoCs. **No** CSI parity claims on the dataset card.

## Pre-flight

```bash
make publish-dry-run
# or:
python training/scripts/publish_dataset.py --checklist
```

Confirm:

- [ ] `training/dataset/v0/*.jsonl` all parse
- [ ] `training/dataset/DATASET_CARD.md` is accurate (Apache-2.0 / CC-BY)
- [ ] No customer dumps, secrets, or unauthorized engagement artifacts
- [ ] Card does **not** claim CSI / alias2-mini superiority

## Auth

```bash
pip install huggingface_hub
huggingface-cli login
# or: export HF_TOKEN=hf_...
```

Create the dataset repo once (use your org/user):

```bash
huggingface-cli repo create YOUR_ORG/firebreak-v0 --type dataset --private
# use --public only after legal review
```

## Upload

```bash
# dry-run first (always)
python training/scripts/publish_dataset.py --repo YOUR_ORG/firebreak-v0

# real upload (requires HF_TOKEN / login)
python training/scripts/publish_dataset.py --upload --repo YOUR_ORG/firebreak-v0
```

Makefile helper (still requires token + `--repo`):

```bash
make publish-upload REPO=YOUR_ORG/firebreak-v0
```

Dataset page: `https://huggingface.co/datasets/YOUR_ORG/firebreak-v0`
