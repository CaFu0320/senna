#!/usr/bin/env python3
"""Train/evaluate a RAW IMU decision tree and export JSON plus deployable C.

Expected input: MEMS Studio CSV logs with accelerometer and gyroscope axes.
The model uses only six raw input columns: ACC_X, ACC_Y, ACC_Z, GYR_X, GYR_Y, GYR_Z.
No engineered features or scaling are added by this script.

Install:
    python -m pip install pandas scikit-learn matplotlib

Example:
    python model_raw.py \
      --curl logs/horizontal.csv \
      --lateralraise logs/static.csv \
      --leftpunch logs/vertical.csv \
      --output-dir raw_tree_results

To convert a previously generated compatible JSON file into C:
    python model_raw.py --convert-json raw_tree_results/decision_tree_raw.json

Important: the C code expects feature values in the SAME units and axis order used
in the CSV training data. Convert STM32 raw integer readings into those units before
calling imu_tree_predict(), or train on raw integer counts instead.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Optional, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    ConfusionMatrixDisplay,
    precision_recall_fscore_support,
)
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier, export_text, plot_tree, _tree

FEATURES = ["ACC_X", "ACC_Y", "ACC_Z", "GYR_X", "GYR_Y", "GYR_Z"]
CLASSES = ["Curl", "LateralRaise", "LeftPunch"]

# Automatic column name recognition. If your CSV headers differ, supply
# --feature-columns followed by the six exact column names in FEATURES order.
ALIASES = {
    "ACC_X": {"accx", "accelx", "accelerometerx", "accelerationx"},
    "ACC_Y": {"accy", "accely", "accelerometery", "accelerationy"},
    "ACC_Z": {"accz", "accelz", "accelerometerz", "accelerationz"},
    "GYR_X": {"gyrx", "gyrox", "gyroscopex", "angularratex", "angvelx"},
    "GYR_Y": {"gyry", "gyroy", "gyroscopey", "angularratey", "angvely"},
    "GYR_Z": {"gyrz", "gyroz", "gyroscopez", "angularratez", "angvelz"},
}


def normalized_column_name(name: str) -> str:
    """Normalize a CSV header and strip common duplicate suffixes."""
    text = str(name).strip()
    text = re.sub(r"\.\d+$", "", text)  # pandas duplicate: ACC_X.1
    text = re.sub(r"__\d+$", "", text)
    return re.sub(r"[^a-z0-9]", "", text.lower())


# Map the logged column names to the six-axis feature order used by the exported model.
def find_feature_columns(columns: Sequence[str], requested: Optional[Sequence[str]]) -> dict[str, str]:
    """Map canonical feature names to actual CSV column names."""
    columns = [str(c) for c in columns]
    if requested:
        if len(requested) != 6:
            raise ValueError("--feature-columns must provide exactly six column names in ACC_X, ACC_Y, ACC_Z, GYR_X, GYR_Y, GYR_Z order.")
        mapping = {}
        for canonical, wanted in zip(FEATURES, requested):
            exact = [c for c in columns if c.strip().lower() == wanted.strip().lower()]
            if not exact:
                raise ValueError(f"Requested column {wanted!r} for {canonical} was not found. Available columns: {columns}")
            mapping[canonical] = exact[0]
        return mapping

    mapping: dict[str, str] = {}
    used: set[str] = set()
    for col in columns:
        norm = normalized_column_name(col)
        for canonical, aliases in ALIASES.items():
            # Accept exact aliases and aliases followed by common unit suffixes.
            recognized = norm in aliases or any(
                norm.startswith(alias) and norm[len(alias):] in {
                    "g", "mg", "ms2", "mss", "dps", "mdps", "radps", "rads", "raw", "count", "counts"
                }
                for alias in aliases
            )
            if recognized and canonical not in mapping and col not in used:
                mapping[canonical] = col
                used.add(col)
    missing = [name for name in FEATURES if name not in mapping]
    if missing:
        raise ValueError(
            "Could not automatically identify the six raw IMU columns. "
            f"Missing: {missing}. CSV columns: {columns}. "
            "Run again with --feature-columns followed by the six exact column names "
            "in this order: ACC_X ACC_Y ACC_Z GYR_X GYR_Y GYR_Z."
        )
    return mapping


def read_memstudio_csv(path: Path) -> pd.DataFrame:
    """Read common MEMS Studio CSV exports, including # comment preambles."""
    if not path.is_file():
        raise FileNotFoundError(f"Input CSV not found: {path}")
    errors = []
    for sep, engine in [(None, "python"), (",", "python"), (";", "python"), ("\t", "python")]:
        try:
            df = pd.read_csv(path, comment="#", skip_blank_lines=True, sep=sep, engine=engine)
            if len(df.columns) >= 2:
                # Drop completely empty columns that can occur with trailing separators.
                df = df.dropna(axis=1, how="all")
                df.columns = [str(c).strip() for c in df.columns]
                return df
        except Exception as exc:  # try the next common delimiter
            errors.append(str(exc))
    raise ValueError(f"Could not read CSV {path}. Parser errors: {'; '.join(errors)}")


def load_one_recording(path: Path, label: str, requested_columns: Optional[Sequence[str]]) -> pd.DataFrame:
    raw = read_memstudio_csv(path)
    mapping = find_feature_columns(raw.columns, requested_columns)
    frame = pd.DataFrame()
    for canonical in FEATURES:
        actual = mapping[canonical]
        frame[canonical] = pd.to_numeric(raw[actual], errors="coerce")
    # Remove rows where any input is missing/non-numeric. Do not scale or derive features.
    frame = frame.replace([np.inf, -np.inf], np.nan).dropna(subset=FEATURES).reset_index(drop=True)
    if len(frame) < 10:
        raise ValueError(
            f"{path} contains only {len(frame)} usable samples after parsing. "
            "Check the header mapping and make sure this is a complete sensor log."
        )
    frame["label"] = label
    frame["source_file"] = path.name
    frame["source_path"] = str(path.resolve())
    frame["source_row"] = np.arange(len(frame), dtype=int)
    used_mapping = ", ".join(f"{key}={value}" for key, value in mapping.items())
    print(f"Loaded {len(frame):,} samples: {path} -> {label}")
    print(f"  Column mapping: {used_mapping}")
    return frame


# Keep acquisition order within a recording so evaluation uses later time blocks.
def split_contiguous_recording(frame: pd.DataFrame, train_fraction: float, validation_fraction: float):
    """Split each recording chronologically, so neighboring rows are not randomly mixed."""
    n = len(frame)
    train_end = int(n * train_fraction)
    validation_end = int(n * (train_fraction + validation_fraction))
    if train_end < 1 or validation_end <= train_end or validation_end >= n:
        raise ValueError(f"Not enough rows ({n}) to create non-empty train/validation/test chunks.")
    pieces = {
        "train": frame.iloc[:train_end].copy(),
        "validation": frame.iloc[train_end:validation_end].copy(),
        "test": frame.iloc[validation_end:].copy(),
    }
    for split_name, piece in pieces.items():
        piece["split"] = split_name
    return pieces


def c_identifier(label: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_]", "_", str(label).upper())
    if not value or value[0].isdigit():
        value = "CLASS_" + value
    return value


def c_float(value: float) -> str:
    value = float(value)
    # Python's repr keeps enough digits for round-trip float serialization.
    text = format(value, ".9g")
    if "e" not in text.lower() and "." not in text:
        text += ".0"
    return text + "f"


# Store every split and leaf, including the input order and class mapping needed for inference.
def export_full_tree_json(model: DecisionTreeClassifier, path: Path) -> dict:
    tree = model.tree_
    class_names = [str(v) for v in model.classes_]
    nodes = []
    for node_id in range(tree.node_count):
        feature_index = int(tree.feature[node_id])
        leaf = feature_index == _tree.TREE_UNDEFINED
        distribution = [float(v) for v in tree.value[node_id][0]]
        predicted_index = int(np.argmax(distribution))
        nodes.append({
            "node_id": node_id,
            "feature_index": None if leaf else feature_index,
            "feature_name": None if leaf else FEATURES[feature_index],
            "threshold": None if leaf else float(tree.threshold[node_id]),
            "left_child": None if leaf else int(tree.children_left[node_id]),
            "right_child": None if leaf else int(tree.children_right[node_id]),
            "is_leaf": bool(leaf),
            "predicted_class_index": predicted_index,
            "predicted_class": class_names[predicted_index] if leaf else None,
            "class_counts": {class_names[i]: distribution[i] for i in range(len(class_names))},
            "samples": int(tree.n_node_samples[node_id]),
            "weighted_samples": float(tree.weighted_n_node_samples[node_id]),
            "impurity": float(tree.impurity[node_id]),
        })
    payload = {
        "format": "imu_decision_tree_v1",
        "description": "Decision tree trained directly on six raw IMU axes; no engineered features or scaling.",
        "features": FEATURES,
        "feature_units_note": "The input values used by firmware must use the same units and axis conventions as the training CSV files.",
        "classes": class_names,
        "node_count": int(tree.node_count),
        "tree_depth": int(model.get_depth()),
        "leaf_count": int(model.get_n_leaves()),
        "nodes": nodes,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


# Generate a static C node table and prediction function from the serialized tree.
def export_json_tree_to_c(json_path: Path, output_prefix: Optional[Path] = None) -> tuple[Path, Path]:
    """Convert the pipeline's full tree JSON to a portable C source/header pair."""
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    required = {"features", "classes", "nodes"}
    if not required.issubset(payload):
        raise ValueError(f"JSON needs keys {sorted(required)}; this does not look like an IMU tree JSON from this script.")
    features = payload["features"]
    classes = payload["classes"]
    nodes = payload["nodes"]
    if not features or not classes or not nodes:
        raise ValueError("Tree JSON has an empty feature, class, or node list.")
    if len(classes) > 254:
        raise ValueError("This generator supports up to 254 output classes.")

    if output_prefix is None:
        output_prefix = json_path.with_suffix("")
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    header_path = output_prefix.with_suffix(".h")
    source_path = output_prefix.with_suffix(".c")
    guard = re.sub(r"[^A-Za-z0-9]", "_", output_prefix.name.upper()) + "_H"

    class_enum_names = ["IMU_CLASS_" + c_identifier(name) for name in classes]
    enum_lines = [f"    {enum_name} = {i}" for i, enum_name in enumerate(class_enum_names)]
    enum_lines.append("    IMU_CLASS_UNKNOWN = 255")
    feature_lines = [f" *   {i}: {feature}" for i, feature in enumerate(features)]
    header = f'''/* Auto-generated from {json_path.name}; do not edit by hand.
 * Feature vector order (float values in training-data units):
{chr(10).join(feature_lines)}
 */
#ifndef {guard}
#define {guard}

#include <stdint.h>

#define IMU_TREE_FEATURE_COUNT ((uint32_t){len(features)}u)
#define IMU_TREE_NODE_COUNT ((uint32_t){len(nodes)}u)

typedef enum {{
{',\n'.join(enum_lines)}
}} imu_tree_class_t;

/* features[] must be in the order listed above and use the same units as training. */
imu_tree_class_t imu_tree_predict(const float features[IMU_TREE_FEATURE_COUNT]);

#endif /* {guard} */
'''
    header_path.write_text(header, encoding="utf-8")

    node_lines = []
    for node in nodes:
        feature_index = node.get("feature_index")
        if feature_index is None:
            feat = -1
            threshold = "0.0f"
            left = -1
            right = -1
        else:
            feat = int(feature_index)
            threshold = c_float(node["threshold"])
            left = int(node["left_child"])
            right = int(node["right_child"])
        class_index = int(node["predicted_class_index"])
        node_lines.append(
            f"    {{{feat}, {threshold}, {left}, {right}, {class_index}u}},"
        )

    source = f'''/* Auto-generated from {json_path.name}; do not edit by hand. */
#include "{header_path.name}"
#include <stddef.h>
#include <stdint.h>

typedef struct {{
    int16_t feature_index; /* -1 indicates a leaf */
    float threshold;
    int32_t left_child;
    int32_t right_child;
    uint8_t predicted_class;
}} imu_tree_node_t;

static const imu_tree_node_t imu_tree_nodes[{len(nodes)}] = {{
{chr(10).join(node_lines)}
}};

imu_tree_class_t imu_tree_predict(const float features[IMU_TREE_FEATURE_COUNT])
{{
    int32_t node_index = 0;
    uint32_t steps;

    if (features == NULL) {{
        return IMU_CLASS_UNKNOWN;
    }}

    /* A valid tree reaches a leaf in fewer steps than the number of nodes.
       The bound also prevents an infinite loop if the table is corrupted. */
    for (steps = 0u; steps < IMU_TREE_NODE_COUNT; ++steps) {{
        const imu_tree_node_t *node;
        float value;

        if (node_index < 0 || (uint32_t)node_index >= IMU_TREE_NODE_COUNT) {{
            return IMU_CLASS_UNKNOWN;
        }}
        node = &imu_tree_nodes[node_index];
        if (node->feature_index < 0) {{
            return (imu_tree_class_t)node->predicted_class;
        }}
        if ((uint32_t)node->feature_index >= IMU_TREE_FEATURE_COUNT) {{
            return IMU_CLASS_UNKNOWN;
        }}
        value = features[node->feature_index];
        if (value <= node->threshold) {{
            node_index = node->left_child;
        }} else {{
            node_index = node->right_child;
        }}
    }}
    return IMU_CLASS_UNKNOWN;
}}
'''
    source_path.write_text(source, encoding="utf-8")
    return source_path, header_path


def evaluate_split(model, frame: pd.DataFrame, split_name: str, out_dir: Path, class_names: list[str]) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    X = frame[FEATURES]
    y_true = frame["label"].astype(str).to_numpy()
    y_pred = model.predict(X)
    accuracy = float(accuracy_score(y_true, y_pred))
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=class_names, zero_division=0
    )
    rows = []
    for i, label in enumerate(class_names):
        rows.append({
            "split": split_name, "class": label, "precision": precision[i],
            "recall": recall[i], "f1_score": f1[i], "support": int(support[i]),
            "accuracy_overall": accuracy,
        })
    # Add macro and weighted averages for a compact, machine-readable report.
    report = classification_report(y_true, y_pred, labels=class_names, target_names=class_names,
                                   output_dict=True, zero_division=0)
    for avg in ("macro avg", "weighted avg"):
        rows.append({
            "split": split_name, "class": avg,
            "precision": report[avg]["precision"], "recall": report[avg]["recall"],
            "f1_score": report[avg]["f1-score"], "support": int(report[avg]["support"]),
            "accuracy_overall": accuracy,
        })
    results = frame[[*FEATURES, "label", "source_file", "source_row"]].copy()
    results["predicted_label"] = y_pred
    results["correct"] = results["label"].astype(str) == results["predicted_label"].astype(str)
    results["split"] = split_name
    return {"accuracy": accuracy, "classification_report": report}, pd.DataFrame(rows), results


# Time host prediction calls on prepared input rows. This excludes sensor acquisition.
def measure_python_latency_us(model, sample: pd.DataFrame, repeats: int = 25, calls_per_repeat: int = 100) -> dict:
    """Estimate scikit-learn single-row prediction latency; not MCU latency."""
    sample = sample.iloc[[0]][FEATURES]
    timings = []
    for _ in range(repeats):
        start = time.perf_counter_ns()
        for _ in range(calls_per_repeat):
            model.predict(sample)
        elapsed = time.perf_counter_ns() - start
        timings.append(elapsed / calls_per_repeat / 1000.0)
    return {
        "python_sklearn_predict_median_us_per_sample": float(np.median(timings)),
        "python_sklearn_predict_mean_us_per_sample": float(np.mean(timings)),
        "timing_method": "Repeated one-row scikit-learn predict calls; includes Python/API overhead and is not MCU latency.",
    }


def save_metrics_plots(model, test_frame: pd.DataFrame, class_names: list[str], out_dir: Path, plot_depth: int):
    # Test-set confusion matrix, numeric CSV and heatmap.
    y_test = test_frame["label"].astype(str).to_numpy()
    y_pred = model.predict(test_frame[FEATURES])
    cm = confusion_matrix(y_test, y_pred, labels=class_names)
    cm_df = pd.DataFrame(cm, index=[f"Actual {c}" for c in class_names],
                         columns=[f"Predicted {c}" for c in class_names])
    cm_df.to_csv(out_dir / "confusion_matrix_test.csv", index=True)
    print("\nTest confusion matrix (rows=actual, columns=predicted):")
    print(cm_df.to_string())

    fig, ax = plt.subplots(figsize=(7, 6))
    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=class_names)
    disp.plot(ax=ax, values_format="d", colorbar=False)
    ax.set_title("RAW IMU decision tree — test confusion matrix")
    fig.tight_layout()
    fig.savefig(out_dir / "confusion_matrix_test.png", dpi=160)
    plt.close(fig)

    # Feature importance ranking and bar chart.
    importance = pd.DataFrame({"feature": FEATURES, "importance": model.feature_importances_})
    importance = importance.sort_values("importance", ascending=False)
    importance.to_csv(out_dir / "feature_importance.csv", index=False)
    fig, ax = plt.subplots(figsize=(8, 5))
    order = importance.sort_values("importance", ascending=True)
    ax.barh(order["feature"], order["importance"])
    ax.set_xlabel("Decision-tree feature importance")
    ax.set_title("RAW IMU feature importance")
    fig.tight_layout()
    fig.savefig(out_dir / "feature_importance.png", dpi=160)
    plt.close(fig)

    # Simplified tree plot: full tree stays in JSON/text; plot is cropped after max depth.
    width = min(24, max(12, model.get_depth() * 2.2))
    height = min(16, max(7, (2 ** min(plot_depth + 1, 5)) * 0.55))
    fig, ax = plt.subplots(figsize=(width, height))
    plot_tree(model, max_depth=plot_depth, feature_names=FEATURES, class_names=class_names,
              filled=False, rounded=True, impurity=True, proportion=False, fontsize=7, ax=ax)
    ax.set_title(f"Decision tree structure (display limited to depth {plot_depth}; full tree in JSON)")
    fig.tight_layout()
    fig.savefig(out_dir / "tree_structure.png", dpi=160)
    plt.close(fig)


def run_training(args) -> None:
    if args.train_fraction <= 0 or args.validation_fraction <= 0 or args.train_fraction + args.validation_fraction >= 1:
        raise ValueError("--train-fraction and --validation-fraction must be > 0 and sum to less than 1.")
    if args.min_samples_leaf < 1 or args.min_samples_split < 2:
        raise ValueError("--min-samples-leaf must be >= 1 and --min-samples-split must be >= 2.")

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    labelled_paths = []
    for label, paths in [("Curl", args.curl), ("LateralRaise", args.lateralraise), ("LeftPunch", args.leftpunch)]:
        if not paths:
            raise ValueError(f"Provide at least one --{label.lower()} CSV file.")
        for raw_path in paths:
            labelled_paths.append((Path(raw_path), label))

    recordings = [(label, load_one_recording(path, label, args.feature_columns))
                  for path, label in labelled_paths]
    counts_by_class = {label: sum(1 for item_label, _ in recordings if item_label == label)
                       for label in CLASSES}
    selected_split_mode = args.split_mode
    # Use whole-session holdouts when each activity has enough independent recordings.
    if selected_split_mode == "auto":
        selected_split_mode = "sessions" if all(counts_by_class[label] >= 3 for label in CLASSES) else "chronological"
    if selected_split_mode == "sessions" and not all(counts_by_class[label] >= 3 for label in CLASSES):
        raise ValueError(
            "Session-based splitting needs at least 3 separate CSV recordings for each class. "
            "Provide more sessions or use --split-mode chronological."
        )

    pieces = {"train": [], "validation": [], "test": []}
    if selected_split_mode == "sessions":
        # Assign entire recording sessions to a single split to reduce temporal leakage.
        rng = np.random.default_rng(args.random_state)
        for label in CLASSES:
            class_sessions = [frame for item_label, frame in recordings if item_label == label]
            order = rng.permutation(len(class_sessions))
            n_sessions = len(class_sessions)
            n_train = max(1, int(round(n_sessions * args.train_fraction)))
            n_validation = max(1, int(round(n_sessions * args.validation_fraction)))
            if n_train + n_validation >= n_sessions:
                n_train = n_sessions - 2
                n_validation = 1
            train_ids = set(order[:n_train].tolist())
            validation_ids = set(order[n_train:n_train + n_validation].tolist())
            for i, frame in enumerate(class_sessions):
                if i in train_ids:
                    split_name = "train"
                elif i in validation_ids:
                    split_name = "validation"
                else:
                    split_name = "test"
                frame_copy = frame.copy()
                frame_copy["split"] = split_name
                pieces[split_name].append(frame_copy)
    else:
        for _, frame in recordings:
            split = split_contiguous_recording(frame, args.train_fraction, args.validation_fraction)
            for name in pieces:
                pieces[name].append(split[name])
        if all(counts_by_class[label] == 1 for label in CLASSES):
            print("WARNING: only one recording per class was supplied. Using chronological blocks; test results do not measure generalization to unseen recording sessions.")
        else:
            print("WARNING: chronological split selected. Different time blocks from a source recording can appear in different partitions.")

    print(f"Split strategy: {selected_split_mode}")
    train_df = pd.concat(pieces["train"], ignore_index=True)
    val_df = pd.concat(pieces["validation"], ignore_index=True)
    test_df = pd.concat(pieces["test"], ignore_index=True)

    # Ensure all classes exist in every partition; otherwise per-class evaluation is misleading.
    for split_name, frame in [("train", train_df), ("validation", val_df), ("test", test_df)]:
        present = set(frame["label"].unique())
        missing = set(CLASSES) - present
        if missing:
            raise ValueError(f"The {split_name} split is missing class(es) {sorted(missing)}. Use longer logs or adjust split fractions.")

    # Fit on training rows only. Each input row is a single IMU sample in the logged units.
    X_train, y_train = train_df[FEATURES], train_df["label"]
    model = DecisionTreeClassifier(
        criterion=args.criterion,
        max_depth=args.max_depth,
        min_samples_leaf=args.min_samples_leaf,
        min_samples_split=args.min_samples_split,
        random_state=args.random_state,
    )
    model.fit(X_train, y_train)
    class_names = [str(value) for value in model.classes_]

    print("\n=== Dataset split ===")
    for name, frame in [("Train", train_df), ("Validation", val_df), ("Test", test_df)]:
        counts = frame["label"].value_counts().to_dict()
        print(f"{name:10s}: {len(frame):,} samples; class counts={counts}")
    print("\n=== Classification reports ===")

    metric_rows = []
    predictions = []
    summary_accuracy = {}
    for split_name, frame in [("train", train_df), ("validation", val_df), ("test", test_df)]:
        details, rows, pred_frame = evaluate_split(model, frame, split_name, out_dir, class_names)
        metric_rows.extend(rows.to_dict("records"))
        predictions.append(pred_frame)
        summary_accuracy[split_name + "_accuracy"] = details["accuracy"]
        print(f"\n{split_name.upper()} (accuracy={details['accuracy']:.4f})")
        print(classification_report(frame["label"].astype(str), model.predict(frame[FEATURES]),
                                   labels=class_names, target_names=class_names, zero_division=0))

    pd.DataFrame(metric_rows).to_csv(out_dir / "metrics_by_class.csv", index=False)
    all_predictions = pd.concat(predictions, ignore_index=True)
    all_predictions.to_csv(out_dir / "predictions_all_splits.csv", index=False)
    # The specifically named test error file contains only test-set mistakes.
    misclassified = all_predictions.loc[
        (all_predictions["split"] == "test") & (~all_predictions["correct"])
    ].copy()
    misclassified.to_csv(out_dir / "test_misclassifications.csv", index=False)

    # Accuracy summary as its own small table.
    pd.DataFrame([{
        "train_accuracy": summary_accuracy["train_accuracy"],
        "validation_accuracy": summary_accuracy["validation_accuracy"],
        "test_accuracy": summary_accuracy["test_accuracy"],
        "generalization_gap_train_minus_test": summary_accuracy["train_accuracy"] - summary_accuracy["test_accuracy"],
        "tree_depth": int(model.get_depth()),
        "leaf_count": int(model.get_n_leaves()),
        "node_count": int(model.tree_.node_count),
    }]).to_csv(out_dir / "accuracy_and_complexity_summary.csv", index=False)

    # Human-readable rules for review and debugging.
    (out_dir / "decision_tree_rules.txt").write_text(
        export_text(model, feature_names=FEATURES, decimals=6), encoding="utf-8"
    )
    json_path = out_dir / "decision_tree_raw.json"
    tree_payload = export_full_tree_json(model, json_path)
    c_source, c_header = export_json_tree_to_c(json_path, out_dir / "decision_tree_raw")

    save_metrics_plots(model, test_df, class_names, out_dir, args.plot_depth)

    latency = measure_python_latency_us(model, test_df)
    json_size_kb = json_path.stat().st_size / 1024.0
    c_size_bytes = c_source.stat().st_size + c_header.stat().st_size
    summary = {
        "model_type": "scikit-learn DecisionTreeClassifier trained on six raw IMU axes",
        "features": FEATURES,
        "classes": class_names,
        "split_mode": selected_split_mode,
        "requested_train_fraction": args.train_fraction,
        "requested_validation_fraction": args.validation_fraction,
        "requested_test_fraction": 1.0 - args.train_fraction - args.validation_fraction,
        "actual_train_sample_fraction": len(train_df) / (len(train_df) + len(val_df) + len(test_df)),
        "actual_validation_sample_fraction": len(val_df) / (len(train_df) + len(val_df) + len(test_df)),
        "actual_test_sample_fraction": len(test_df) / (len(train_df) + len(val_df) + len(test_df)),
        "criterion": args.criterion,
        "max_depth_setting": args.max_depth,
        "min_samples_leaf": args.min_samples_leaf,
        "min_samples_split": args.min_samples_split,
        "train_samples": len(train_df),
        "validation_samples": len(val_df),
        "test_samples": len(test_df),
        **summary_accuracy,
        "generalization_gap_train_minus_test": summary_accuracy["train_accuracy"] - summary_accuracy["test_accuracy"],
        "tree_depth": int(model.get_depth()),
        "leaf_count": int(model.get_n_leaves()),
        "node_count": int(model.tree_.node_count),
        "json_file": json_path.name,
        "json_size_kb": round(json_size_kb, 3),
        "c_source_and_header_combined_bytes": c_size_bytes,
        **latency,
        "important_evaluation_note": ("Entire recording sessions are assigned to train/validation/test when at least three recordings per class are provided." if selected_split_mode == "sessions" else "Chronological blocks from each recording are used because there are not at least three recordings per class. With only one recording per class, results do not test generalization to unseen recording sessions; collect independent sessions for a stronger evaluation."),
        "embedded_latency_note": "Python latency is not STM32 latency. Measure the generated C function on the target hardware for the deployed inference estimate.",
    }
    (out_dir / "model_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n=== Model complexity and exports ===")
    print(f"Tree depth: {model.get_depth()}")
    print(f"Leaves: {model.get_n_leaves()}")
    print(f"Nodes: {model.tree_.node_count}")
    print(f"Serialized tree JSON size: {json_size_kb:.3f} KB")
    print(f"Python sklearn prediction latency estimate: {latency['python_sklearn_predict_median_us_per_sample']:.2f} us/sample (not MCU timing)")
    print(f"\nAll outputs saved to: {out_dir.resolve()}")
    print(f"JSON: {json_path}")
    print(f"C source: {c_source}")
    print(f"C header: {c_header}")
    if selected_split_mode == "sessions":
        print("\nNote: train/validation/test use separate recording sessions.")
    else:
        print("\nNote: train/validation/test are chronological blocks within each recording.")
        print("For reliable session-independent performance, collect at least three separate logs per class.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train/evaluate a RAW IMU decision tree, export JSON, and generate C for embedded inference."
    )
    parser.add_argument("--curl", nargs="+", help="One or more Curl CSV log files")
    parser.add_argument("--lateralraise", nargs="+", help="One or more LateralRaise CSV log files")
    parser.add_argument("--leftpunch", nargs="+", help="One or more LeftPunch CSV log files")
    parser.add_argument("--feature-columns", nargs=6, metavar=("ACC_X", "ACC_Y", "ACC_Z", "GYR_X", "GYR_Y", "GYR_Z"),
                        help="Exact CSV column names in this order; use if auto-detection fails")
    parser.add_argument("--output-dir", default="raw_tree_results", help="Folder for metrics, plots, JSON, and C files")
    parser.add_argument("--train-fraction", type=float, default=0.70, help="Chronological fraction per recording used for training (default 0.70)")
    parser.add_argument("--validation-fraction", type=float, default=0.15, help="Next chronological fraction for validation (default 0.15); rest is test")
    parser.add_argument("--max-depth", type=int, default=None, help="Maximum tree depth; set to the same value as earlier tasks when required")
    parser.add_argument("--min-samples-leaf", type=int, default=1)
    parser.add_argument("--min-samples-split", type=int, default=2)
    parser.add_argument("--criterion", choices=["gini", "entropy", "log_loss"], default="gini")
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--split-mode", choices=["auto", "chronological", "sessions"], default="auto",
                        help="auto uses whole-session splits when >=3 files/class; otherwise chronological blocks")
    parser.add_argument("--plot-depth", type=int, default=3, help="Maximum depth drawn in simplified tree visualization")
    parser.add_argument("--convert-json", type=Path, help="Only convert an existing compatible full tree JSON to C; skips training")
    parser.add_argument("--c-out-prefix", type=Path, help="C output prefix for --convert-json; default is JSON path without suffix")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.convert_json:
            if not args.convert_json.is_file():
                raise FileNotFoundError(f"JSON tree file not found: {args.convert_json}")
            source_path, header_path = export_json_tree_to_c(args.convert_json, args.c_out_prefix)
            print(f"Generated C source: {source_path}")
            print(f"Generated C header: {header_path}")
            print("Check feature order and units in the generated header before calling from STM32 firmware.")
            return 0
        if not (args.curl and args.lateralraise and args.leftpunch):
            parser.error("Training needs all three groups: --curl, --lateralraise, and --leftpunch. For JSON-only conversion, use --convert-json FILE.")
        if args.plot_depth < 0:
            raise ValueError("--plot-depth must be zero or greater.")
        run_training(args)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
