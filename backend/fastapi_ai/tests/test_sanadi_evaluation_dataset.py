from pathlib import Path

from psychology.evaluation.dataset_schema import load_eval_samples


def test_sanadi_eval_dataset_loads() -> None:
    dataset_path = (
        Path(__file__).resolve().parents[1] / "psychology" / "evaluation" / "data" / "sanadi_evalset.jsonl"
    )
    samples = load_eval_samples(dataset_path)
    assert len(samples) >= 5
    assert samples[0].sample_id.startswith("sanadi_eval_")
