# Firebreak open dataset (Wave 3)

Versioned JSONL releases for community fine-tuning.

## Generate a local snapshot

```bash
PYTHONPATH=src python3 -c "
from pathlib import Path
from orchestrator.dataset.pipeline import synthetic_from_inventory, write_jsonl
n = write_jsonl(Path('training/dataset/v0/synthetic_inventory.jsonl'), synthetic_from_inventory())
print('wrote', n)
"
```

License: Apache-2.0 for synthetic inventory rows. Do not add proprietary CSI corpora.
