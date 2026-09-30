"""Feature preparation: train-fitted imputation, encoding, gene selection, scaling."""
from __future__ import annotations

import re

import pandas as pd


def excluded_gene_set(columns, excluded_genes=(), excluded_gene_patterns=()) -> list:
    """Columns to exclude: explicit names plus any matching a configured regex."""
    pats = [re.compile(p) for p in excluded_gene_patterns]
    names = set(excluded_genes)
    return [c for c in columns if c in names or any(p.search(c) for p in pats)]


def prepare_features(patients: pd.DataFrame, expr: pd.DataFrame | None,
                     train_ids: list, test_ids: list,
                     covariate_kinds: dict, n_expression_genes: int,
                     include_expression: bool, excluded_genes: list | tuple = (),
                     excluded_gene_patterns: list | tuple = ()):
    """Return X_train, X_test, meta. All statistics fitted on train only."""
    meta = {"feature_kinds": {}, "impute": {}, "scale": {}, "gene_cols": [],
            "reference_levels": {}}
    train = patients.loc[train_ids]
    test = patients.loc[test_ids]

    tr_frames, te_frames = [], []
    for col, kind in sorted(covariate_kinds.items()):
        if kind == "numeric" or kind == "binary":
            fill = float(train[col].median()) if train[col].notna().any() else 0.0
            meta["impute"][col] = fill
            tr_frames.append(train[col].fillna(fill))
            te_frames.append(test[col].fillna(fill))
            meta["feature_kinds"][col] = kind
        else:  # categorical: mode-impute on train, k-1 dummies vs first sorted level
            cats = sorted(train[col].dropna().unique())
            ref = cats[0] if cats else None
            modes = train[col].mode()
            mode = modes.iloc[0] if len(modes) else ref
            meta["impute"][col] = mode
            meta["reference_levels"][col] = ref
            tr_col = train[col].fillna(mode)
            te_col = test[col].fillna(mode)
            for c in cats[1:]:
                name = f"{col}_{c}"
                tr_frames.append((tr_col == c).astype(float).rename(name))
                te_frames.append((te_col == c).astype(float).rename(name))
                meta["feature_kinds"][name] = "dummy"

    X_train = pd.concat(tr_frames, axis=1).astype(float)
    X_test = pd.concat(te_frames, axis=1).astype(float)[X_train.columns]

    if include_expression and expr is not None and n_expression_genes:
        drop = excluded_gene_set(expr.columns, excluded_genes, excluded_gene_patterns)
        expr_train = expr.loc[train_ids].drop(columns=drop)
        expr_test = expr.loc[test_ids].drop(columns=drop)
        gene_cols = list(expr_train.var().sort_values(ascending=False)
                         .head(n_expression_genes).index)
        meta["gene_cols"] = gene_cols
        sub_tr, sub_te = expr_train[gene_cols], expr_test[gene_cols]
        med = sub_tr.median()
        sub_tr = sub_tr.fillna(med)
        sub_te = sub_te.fillna(med)
        mean, sd = sub_tr.mean(), sub_tr.std(ddof=1).replace(0, 1.0)
        meta["scale"] = {g: (float(mean[g]), float(sd[g])) for g in gene_cols}
        X_train = pd.concat([X_train, (sub_tr - mean) / sd], axis=1)
        X_test = pd.concat([X_test, (sub_te - mean) / sd], axis=1)

    return X_train, X_test, meta
