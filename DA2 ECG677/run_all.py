"""Regenerate Tasks 1–5 and the Task 6 software comparison."""
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
CLASSES = ["Curl", "LateralRaise", "LeftPunch"]

def run(script, *args):
    subprocess.run([sys.executable, f"src/{script}.py", *args], cwd=ROOT, check=True)

def main():
    run("data_preparation", "--out-dir", "docs/task1")
    scripts = ["model_raw", "model_raw_fe", "model_quaternion", "model_quaternion_fe"]
    for task, script in enumerate(scripts, 2):
        directory = f"docs/task{task}"
        args = ["--output-dir", directory]
        for label in CLASSES:
            path = f"data/raw/{label}.csv" if task < 4 else f"data/quatlogs/{label}_Q.csv"
            args.extend([f"--{label.lower()}", path])
        if task == 3:
            args.extend(["--raw-summary", "docs/task2/model_summary.json"])
        if task == 5:
            args.extend(["--rawfe-summary", "docs/task3/model_summary.json"])
        run(script, *args)
        (ROOT / "models").mkdir(exist_ok=True)
        for path in (ROOT / directory).glob("decision_tree*"):
            if path.suffix in {".json", ".c", ".h"}:
                shutil.copy2(path, ROOT / "models" / path.name)
    args = [arg for task in range(2, 6) for arg in (f"--task{task}", f"docs/task{task}")]
    for label in CLASSES:
        args.extend([f"--{label.lower()}", f"data/raw/{label}.csv"])
    run("comparison_analysis", *args, "--quat-dir", "data/quatlogs", "--out", "docs/comparison")

if __name__ == "__main__":
    main()
