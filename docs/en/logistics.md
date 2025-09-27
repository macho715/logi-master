# Logistics Validation Guide

## Overview

Use `python devmind.py logistics-validate --payload shipment.json` to validate logistics payloads against Incoterm 2020, HS 2022, and AED-centric currency policies.

## Usage Notes

- `incoterm`: must exist in `/resources/incoterm.yaml`.
- `hs_code`: matched against `resources/hs2022.csv` and normalized to six digits.
- `currency`: defaults to AED; allowed values are `AED`, `USD`, `EUR`, and `SAR`.
- `declared_value`: rounded to two decimal places with half-up semantics.

## Output

The command prints a JSON array of summaries that can be piped into reports or journal steps.
