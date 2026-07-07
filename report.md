# Data Analyst Agent Report

**Goal:** 找出销售数据里的主要模式

## Dataset Profile

- Source: `examples\sales.csv`
- Shape: 10 rows x 5 columns
- Columns: region, product, units, revenue, discount

## Data Quality

- No obvious duplicate, missing-value, or constant-column issues detected.

## Findings

### Dataset size and schema

```json
{
  "rows": 10,
  "columns": 5,
  "column_names": [
    "region",
    "product",
    "units",
    "revenue",
    "discount"
  ]
}
```

### Data quality scan

```json
{
  "missing_values": {
    "region": 0,
    "product": 0,
    "units": 0,
    "revenue": 0,
    "discount": 0
  },
  "duplicate_rows": 0
}
```

### Numeric summary

```json
{
  "units": {
    "count": 10.0,
    "mean": 33.8,
    "std": 33.75,
    "min": 4.0,
    "25%": 7.5,
    "50%": 13.5,
    "75%": 58.75,
    "max": 90.0
  },
  "revenue": {
    "count": 10.0,
    "mean": 1436.5,
    "std": 1048.099,
    "min": 275.0,
    "25%": 412.5,
    "50%": 1535.0,
    "75%": 2250.0,
    "max": 3150.0
  },
  "discount": {
    "count": 10.0,
    "mean": 0.045,
    "std": 0.046,
    "min": 0.0,
    "25%": 0.0,
    "50%": 0.04,
    "75%": 0.078,
    "max": 0.12
  }
}
```

### Top values for region

```json
[
  {
    "region": "West",
    "row_count": 3
  },
  {
    "region": "East",
    "row_count": 3
  },
  {
    "region": "South",
    "row_count": 2
  },
  {
    "region": "North",
    "row_count": 2
  }
]
```

### Numeric correlations

```json
[
  {
    "left": "units",
    "right": "discount",
    "correlation": -0.849
  },
  {
    "left": "units",
    "right": "revenue",
    "correlation": -0.804
  },
  {
    "left": "revenue",
    "right": "discount",
    "correlation": 0.542
  }
]
```


## Next Steps

- Validate surprising findings with domain knowledge.
- Add goal-specific metrics once the target business question is known.
- Promote any repeated analysis into a tested reusable tool.