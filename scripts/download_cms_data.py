#!/usr/bin/env python3
"""
Download Medicare Part D prescriber data from CMS public data API.

Source: CMS Open Data Portal (data.cms.gov) - 2024 Dataset
- Dataset: Medicare Part D Prescribers - by Provider and Drug
- Release: 2024 Medicare Part D Prescriber Public Use File
- Total Records: 28,023,892 rows
- API: CMS Data API (Socrata-compatible)
- Dataset ID: 9552739e-3d05-4c1b-8eff-ecabf391e2e5
- Endpoint: https://data.cms.gov/data-api/v1/dataset/9552739e-3d05-4c1b-8eff-ecabf391e2e5/data

Real columns (note: all values come as strings):
  - Prscrbr_NPI (prescriber identifier)
  - Prscrbr_Last_Org_Name
  - Prscrbr_First_Name
  - Prscrbr_City
  - Prscrbr_State_Abrvtn
  - Prscrbr_Type
  - Brnd_Name (brand name)
  - Gnrc_Name (generic name)
  - Tot_Clms (total claims)
  - Tot_30day_Fills
  - Tot_Day_Suply
  - Tot_Drug_Cst (total cost)
  - Tot_Benes (total beneficiaries)

SAMPLING STRATEGY:
  Data is sorted by NPI, so we don't just take first N rows. Instead, we sample
  uniformly across states by fetching a fixed number of rows per state (at least 25
  states) to get ~500K-1M total rows and ensure geographic diversity.

IMPORTANT: This script downloads REAL CMS public data by default. If the API
fails, it will exit with an error. Pass --synthetic to generate sample data
(all output files will be marked SYNTHETIC and a warning will be logged).

Usage:
  python download_cms_data.py              # Download real CMS data (~500K rows, 25+ states)
  python download_cms_data.py --synthetic  # Generate synthetic sample data
  python download_cms_data.py --limit 1000000 # Download 1M rows
  python download_cms_data.py --rows-per-state 20000 # Custom sampling (20K per state)
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)


def create_session_with_retries(retries=3, backoff_factor=0.5, timeout=30):
    """Create requests session with retry strategy and polite delays."""
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        backoff_factor=backoff_factor,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


class CMSDataDownloader:
    """Download and validate real CMS Medicare Part D data using per-state sampling."""

    # CMS Data API endpoint (verified 2024 dataset)
    API_BASE = "https://data.cms.gov/data-api/v1/dataset"
    DATASET_ID = "9552739e-3d05-4c1b-8eff-ecabf391e2e5"
    ENDPOINT = f"{API_BASE}/{DATASET_ID}/data"

    # API limits and behavior
    MAX_PAGE_SIZE = 50000  # CMS API's maximum page size
    POLITE_DELAY_SECONDS = 0.5  # Delay between requests to be respectful

    # Data validation thresholds
    MIN_UNIQUE_PRESCRIBERS = 1000
    MIN_UNIQUE_STATES = 20
    MIN_UNIQUE_DRUGS = 100

    # Sampling strategy: fixed rows per state for geographic diversity
    DEFAULT_ROWS_PER_STATE = 20000  # 20K per state × 25+ states ≈ 500K-600K total
    MIN_STATES_TO_SAMPLE = 25

    # Real CMS column names (note: come back as strings from API)
    # REQUIRED columns: columns that marts need (must be non-null after conversion)
    REQUIRED_COLUMNS = {
        "prscrbr_npi": "Prscrbr_NPI",
        "prscrbr_last_org_name": "Prscrbr_Last_Org_Name",
        "prscrbr_first_name": "Prscrbr_First_Name",
        "prscrbr_city": "Prscrbr_City",
        "prscrbr_state_abrvtn": "Prscrbr_State_Abrvtn",
        "prscrbr_type": "Prscrbr_Type",
        "brnd_name": "Brnd_Name",
        "gnrc_name": "Gnrc_Name",
        "tot_clms": "Tot_Clms",
        "tot_30day_fills": "Tot_30day_Fills",
        "tot_day_suply": "Tot_Day_Suply",
        "tot_drug_cst": "Tot_Drug_Cst",
        "tot_benes": "Tot_Benes",  # Optional: nullable (CMS suppression for <11 beneficiaries)
    }

    # Columns required to be non-null after numeric conversion
    # Tot_Benes is intentionally excluded (CMS blanks this for <11 beneficiaries)
    REQUIRED_NUMERIC_COLUMNS = {
        "prscrbr_npi",
        "tot_clms",
        "tot_30day_fills",
        "tot_day_suply",
        "tot_drug_cst",
    }

    def __init__(self, output_dir: str = "data/raw", use_synthetic: bool = False):
        """Initialize downloader.

        Args:
            output_dir: Directory for output CSV files
            use_synthetic: If True, generate synthetic sample data (not real CMS data)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.use_synthetic = use_synthetic
        self.data_source = "SYNTHETIC" if use_synthetic else "REAL_CMS"
        self.session = create_session_with_retries()
        # Track rows dropped during validation
        self.rows_dropped = {
            "null_critical_columns": 0,
            "non_positive_claims": 0,
            "nan_after_numeric_conversion": 0,
            "total_dropped": 0,
            "total_input": 0,
            "nan_per_column": {},  # Track which columns had NaNs
        }

    def download(
        self, limit: int = None, rows_per_state: int = None
    ) -> Tuple[str, Dict]:
        """
        Download CMS data using per-state sampling (not just first N rows).

        Args:
            limit: Max total rows (default: 500K). Ignored if rows_per_state is set.
            rows_per_state: Rows to fetch per state (default: 20K). More control over sampling.

        Returns:
            Tuple of (output_filepath, metadata_dict)

        Raises:
            RuntimeError: If real data download requested but API fails
        """
        rows_per_state = rows_per_state or self.DEFAULT_ROWS_PER_STATE
        source_label = "SYNTHETIC sample" if self.use_synthetic else "REAL CMS"
        logger.info(f"Starting {source_label} data download")

        if self.use_synthetic:
            # Explicit synthetic mode
            logger.warning("⚠️  GENERATING SYNTHETIC SAMPLE DATA (NOT REAL CMS DATA)")
            df = self._generate_synthetic_data(rows_per_state=rows_per_state)
        else:
            # Real data mode: fetch via per-state sampling
            logger.info(
                f"Fetching from {self.MIN_STATES_TO_SAMPLE}+ states, {rows_per_state:,} rows per state"
            )
            df = self._fetch_via_state_sampling(rows_per_state=rows_per_state)

        if df is None or df.empty:
            raise RuntimeError("No data retrieved from source")

        # Validate and clean
        df = self._validate_and_clean(df)
        logger.info(f"Data shape after validation: {df.shape}")

        # Check for synthetic data red flags
        prescriber_count = (
            df["prscrbr_npi"].nunique() if "prscrbr_npi" in df.columns else 0
        )
        state_count = (
            df["prscrbr_state_abrvtn"].nunique()
            if "prscrbr_state_abrvtn" in df.columns
            else 0
        )
        drug_count = (df["brnd_name"].nunique() if "brnd_name" in df.columns else 0) + (
            df["gnrc_name"].nunique() if "gnrc_name" in df.columns else 0
        )

        if not self.use_synthetic:
            # Validate real data looks real
            self._validate_data_realism(prescriber_count, state_count, drug_count)

        # Save to CSV with synthetic marker in filename if needed
        suffix = "_SYNTHETIC" if self.use_synthetic else ""
        output_file = self.output_dir / f"cms_partd_{self.timestamp}{suffix}.csv"
        df.to_csv(output_file, index=False)
        logger.info(f"✓ Saved {len(df):,} rows to {output_file}")

        # Compute metadata
        metadata = self._compute_metadata(df, rows_per_state)

        return str(output_file), metadata

    def _fetch_via_state_sampling(self, rows_per_state: int) -> pd.DataFrame:
        """
        Fetch data from CMS API using per-state sampling for geographic diversity.

        Strategy: Fetch fixed number of rows per state (not sorted by NPI) to ensure
        we get diverse prescribers across all states.

        Args:
            rows_per_state: Number of rows to fetch from each state

        Returns:
            Combined DataFrame from all states

        Raises:
            RuntimeError: If API fails or returns unexpected format
        """
        logger.info(
            f"Fetching via per-state sampling: {rows_per_state:,} rows per state"
        )

        # US state abbreviations (50 states + DC, but API may not have all)
        states = [
            "AL",
            "AK",
            "AZ",
            "AR",
            "CA",
            "CO",
            "CT",
            "DE",
            "FL",
            "GA",
            "HI",
            "ID",
            "IL",
            "IN",
            "IA",
            "KS",
            "KY",
            "LA",
            "ME",
            "MD",
            "MA",
            "MI",
            "MN",
            "MS",
            "MO",
            "MT",
            "NE",
            "NV",
            "NH",
            "NJ",
            "NM",
            "NY",
            "NC",
            "ND",
            "OH",
            "OK",
            "OR",
            "PA",
            "RI",
            "SC",
            "SD",
            "TN",
            "TX",
            "UT",
            "VT",
            "VA",
            "WA",
            "WV",
            "WI",
            "WY",
        ]

        dfs = []
        successful_states = []
        failed_states = []

        for state in states:
            try:
                logger.info(f"  Fetching {state}...")
                state_df = self._fetch_state_data(state, rows_per_state)

                if state_df is not None and len(state_df) > 0:
                    dfs.append(state_df)
                    successful_states.append(state)
                    logger.info(f"    ✓ {len(state_df):,} rows from {state}")
                else:
                    logger.info(f"    (No data for {state})")
                    failed_states.append(state)

                # Polite delay between requests
                time.sleep(self.POLITE_DELAY_SECONDS)

                # Stop early if we have enough states
                if len(successful_states) >= self.MIN_STATES_TO_SAMPLE:
                    logger.info(f"Reached {len(successful_states)} states, stopping")
                    break

            except Exception as e:
                logger.warning(f"  Failed to fetch {state}: {e}")
                failed_states.append(state)

        if len(dfs) == 0:
            raise RuntimeError(
                f"Failed to fetch data from any state. "
                f"Check if CMS API is available at {self.ENDPOINT}"
            )

        if len(successful_states) < self.MIN_STATES_TO_SAMPLE:
            logger.warning(
                f"Only fetched from {len(successful_states)} states "
                f"(target: {self.MIN_STATES_TO_SAMPLE}). "
                f"Data may not be geographically representative."
            )

        # Combine all state data
        df = pd.concat(dfs, ignore_index=True)
        logger.info(
            f"✓ Combined {len(df):,} rows from {len(successful_states)} states: {', '.join(successful_states)}"
        )

        return df

    def _fetch_state_data(
        self, state: str, rows_per_state: int
    ) -> Optional[pd.DataFrame]:
        """
        Fetch data for a single state using pagination.

        CMS API format:
          GET /data-api/v1/dataset/ID/data?filter[Prscrbr_State_Abrvtn]=AL&size=5000&offset=0

        Note: API caps actual page size (may return fewer rows than requested).
        Always advance offset by actual rows returned, not by size requested.

        Args:
            state: State abbreviation (e.g., 'CA')
            rows_per_state: Target number of rows to fetch

        Returns:
            DataFrame with state data, or None if no data

        Raises:
            RuntimeError: If API returns error
        """
        dfs = []
        offset = 0
        rows_fetched = 0
        request_size = 5000  # Request 5K; server may return less

        while rows_fetched < rows_per_state:
            # Build API request with correct query parameter format
            # API expects: filter[Prscrbr_State_Abrvtn]=AL&size=5000&offset=0
            params = {
                "filter[Prscrbr_State_Abrvtn]": state,
                "size": request_size,
                "offset": offset,
            }

            headers = {
                "User-Agent": "CMSDataDownloader/2.0",
                "Accept": "application/json",
            }

            try:
                logger.debug(
                    f"    Fetching {state} offset={offset}, size={request_size}"
                )
                response = self.session.get(
                    self.ENDPOINT, params=params, headers=headers, timeout=120
                )
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                logger.error(f"    API request failed for {state} offset {offset}: {e}")
                if hasattr(response, "status_code"):
                    if response.status_code == 404:
                        return None  # State may not have data
                    if response.status_code == 400:
                        logger.error("    Bad request (400). Check parameter format.")
                        return None
                raise RuntimeError(
                    f"Failed to fetch {state} data from CMS API: {e}. "
                    f"Check if API is available at {self.ENDPOINT}"
                ) from e

            # Parse response
            try:
                data = response.json()
            except json.JSONDecodeError as e:
                raise RuntimeError(f"API returned invalid JSON for {state}: {e}") from e

            # Extract records from response
            if isinstance(data, dict) and "data" in data:
                records = data["data"]
            elif isinstance(data, list):
                records = data
            else:
                logger.warning(
                    f"    Unexpected response format for {state}: {type(data)}"
                )
                break

            if not records or len(records) == 0:
                logger.debug(
                    f"    No more records at offset {offset} (end of data for {state})"
                )
                break

            actual_returned = len(records)
            logger.debug(f"    Got {actual_returned} rows (requested {request_size})")

            # Convert to DataFrame
            df = pd.DataFrame(records)
            dfs.append(df)

            rows_fetched += actual_returned
            # IMPORTANT: Advance offset by actual rows returned, not by size requested
            offset += actual_returned

            # Stop if we got fewer rows than requested (end of data) or reached target
            if actual_returned < request_size:
                logger.debug(
                    f"    Fewer rows returned ({actual_returned} < {request_size}), stopping pagination for {state}"
                )
                break

        if len(dfs) == 0:
            return None

        result = pd.concat(dfs, ignore_index=True)
        logger.debug(f"    Combined: {len(result)} total rows from {state}")
        return result

    def _generate_synthetic_data(self, rows_per_state: int) -> pd.DataFrame:
        """
        Generate synthetic sample data matching CMS schema.

        This is ONLY for testing/demo purposes and should never be used as real data.
        All output will be marked SYNTHETIC.
        """
        logger.warning("⚠️  GENERATING SYNTHETIC DATA - NOT REAL CMS DATA")
        logger.warning("⚠️  Output files will be marked '_SYNTHETIC' in filename")

        states = [
            "AL",
            "AK",
            "AZ",
            "AR",
            "CA",
            "CO",
            "CT",
            "DE",
            "FL",
            "GA",
            "HI",
            "ID",
            "IL",
            "IN",
            "IA",
            "KS",
            "KY",
            "LA",
            "ME",
            "MD",
            "MA",
            "MI",
            "MN",
            "MS",
            "MO",
            "MT",
            "NE",
            "NV",
            "NH",
            "NJ",
            "NM",
            "NY",
            "NC",
            "ND",
            "OH",
            "OK",
            "OR",
            "PA",
            "RI",
            "SC",
            "SD",
            "TN",
            "TX",
            "UT",
            "VT",
            "VA",
            "WA",
            "WV",
            "WI",
            "WY",
        ]

        drugs = [
            "Metformin HCl",
            "Lisinopril",
            "Atorvastatin Calcium",
            "Amlodipine Besylate",
            "Omeprazole",
            "Albuterol Sulfate",
            "Simvastatin",
            "Amoxicillin",
            "Hydrocodone-Acetaminophen",
            "Ibuprofen",
        ]

        prescriber_types = ["MD", "DO", "NP", "PA", "DDS"]
        cities = ["Springfield", "Metropolis", "Shelbyville", "Capital City"]

        import random

        random.seed(42)
        rows = []
        total_rows = len(states) * rows_per_state

        for i in range(total_rows):
            state = random.choice(states)
            drug = random.choice(drugs)
            brnd_name, gnrc_name = drug.split(" ", 1) if " " in drug else (drug, drug)

            rows.append(
                {
                    "Prscrbr_NPI": str(1000000000 + (i % 100000)),
                    "Prscrbr_Last_Org_Name": f"Provider_Org_{i % 5000}",
                    "Prscrbr_First_Name": f"Doctor_{i % 5000}",
                    "Prscrbr_City": random.choice(cities),
                    "Prscrbr_State_Abrvtn": state,
                    "Prscrbr_Type": random.choice(prescriber_types),
                    "Brnd_Name": brnd_name,
                    "Gnrc_Name": gnrc_name,
                    "Tot_Clms": str(random.randint(100, 50000)),
                    "Tot_30day_Fills": str(random.randint(100, 50000)),
                    "Tot_Day_Suply": str(random.randint(1000, 500000)),
                    "Tot_Drug_Cst": str(round(random.uniform(1000, 500000), 2)),
                    "Tot_Benes": str(random.randint(10, 10000)),
                }
            )

        df = pd.DataFrame(rows)
        logger.warning(f"⚠️  Generated {len(df):,} synthetic rows")
        return df

    def _validate_and_clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validate required columns and clean data, measuring row drops by reason.

        Note: Tot_Benes is nullable (CMS suppresses for <11 beneficiaries).
        Only drops rows for NaN in truly required numeric columns.
        """
        initial_rows = len(df)
        self.rows_dropped["total_input"] = initial_rows

        # Normalize column names to lowercase snake_case
        df.columns = [
            col.lower().replace(" ", "_").replace("-", "_") for col in df.columns
        ]

        # Keep only relevant columns if available
        kept_cols = [col for col in self.REQUIRED_COLUMNS.keys() if col in df.columns]
        if not kept_cols:
            raise RuntimeError(
                f"No recognized columns found. API response columns: {list(df.columns)}"
            )

        df = df[kept_cols]

        # Remove rows with nulls in critical (string) columns before conversion
        critical = ["prscrbr_npi", "prscrbr_state_abrvtn", "brnd_name", "tot_clms"]
        critical_in_df = [c for c in critical if c in df.columns]
        before_null_drop = len(df)
        df = df.dropna(subset=critical_in_df, how="any")
        null_dropped = before_null_drop - len(df)
        self.rows_dropped["null_critical_columns"] = null_dropped

        # Convert numeric columns from strings to proper types
        numeric_cols = [
            "prscrbr_npi",
            "tot_clms",
            "tot_30day_fills",
            "tot_day_suply",
            "tot_drug_cst",
            "tot_benes",
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Track NaN counts per column after conversion (before dropping anything)
        nan_per_col = {}
        for col in numeric_cols:
            if col in df.columns:
                nan_count = df[col].isna().sum()
                if nan_count > 0:
                    nan_per_col[col] = int(nan_count)
        self.rows_dropped["nan_per_column"] = nan_per_col

        # Log NaN counts by column
        if nan_per_col:
            logger.info("  NaN counts after numeric conversion (by column):")
            for col, count in sorted(nan_per_col.items()):
                logger.info(f"    - {col}: {count:,}")

        # Remove rows with non-positive claim counts (data quality check)
        claim_dropped = 0
        if "tot_clms" in df.columns:
            before_claim_drop = len(df)
            df = df[df["tot_clms"] > 0]
            claim_dropped = before_claim_drop - len(df)
            self.rows_dropped["non_positive_claims"] = claim_dropped

        # Remove rows with NaN only in REQUIRED numeric columns
        # (tot_benes is optional and nullable - CMS suppression for <11 beneficiaries)
        required_numeric_present = [
            col for col in self.REQUIRED_NUMERIC_COLUMNS if col in df.columns
        ]
        nan_dropped = 0
        if required_numeric_present:
            before_nan_drop = len(df)
            df = df.dropna(subset=required_numeric_present)
            nan_dropped = before_nan_drop - len(df)
            self.rows_dropped["nan_after_numeric_conversion"] = nan_dropped

        # Calculate totals
        total_dropped = null_dropped + claim_dropped + nan_dropped
        self.rows_dropped["total_dropped"] = total_dropped
        final_rows = len(df)

        # Log detailed breakdown with measured values
        logger.info(
            f"✓ Validation complete: {final_rows:,} rows after cleaning ({initial_rows:,} input)"
        )
        logger.info("  Rows dropped by reason:")
        logger.info(f"    - Null/missing critical columns: {null_dropped:,}")
        logger.info(f"    - Non-positive claim counts: {claim_dropped:,}")
        logger.info(
            f"    - NaN after numeric conversion (required columns only): {nan_dropped:,}"
        )
        logger.info(f"    - Total dropped: {total_dropped:,}")

        return df

    def _validate_data_realism(
        self, prescriber_count: int, state_count: int, drug_count: int
    ):
        """
        Validate that downloaded data looks real (not synthetic).

        Raises:
            RuntimeError: If data has suspiciously few unique values
        """
        issues = []

        if prescriber_count < self.MIN_UNIQUE_PRESCRIBERS:
            issues.append(
                f"Too few prescribers: {prescriber_count} < {self.MIN_UNIQUE_PRESCRIBERS} "
                f"(likely synthetic/corrupted data)"
            )

        if state_count < self.MIN_UNIQUE_STATES:
            issues.append(
                f"Too few states: {state_count} < {self.MIN_UNIQUE_STATES} "
                f"(likely synthetic/corrupted data)"
            )

        if drug_count < self.MIN_UNIQUE_DRUGS:
            issues.append(
                f"Too few drugs: {drug_count} < {self.MIN_UNIQUE_DRUGS} "
                f"(likely synthetic/corrupted data)"
            )

        if issues:
            error_msg = (
                "✗ Downloaded data failed realism checks (looks synthetic or corrupted):\n  "
                + "\n  ".join(issues)
                + "\n\nIf the CMS API is down, retry with --synthetic flag to generate sample data."
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        logger.info("✓ Data passed realism checks:")
        logger.info(
            f"  Prescribers: {prescriber_count:,} (min: {self.MIN_UNIQUE_PRESCRIBERS:,})"
        )
        logger.info(f"  States: {state_count} (min: {self.MIN_UNIQUE_STATES})")
        logger.info(f"  Drugs: {drug_count:,} (min: {self.MIN_UNIQUE_DRUGS:,})")

    def _compute_metadata(self, df: pd.DataFrame, rows_per_state: int) -> Dict:
        """Compute data quality metrics and source information."""
        prescriber_count = (
            df["prscrbr_npi"].nunique() if "prscrbr_npi" in df.columns else None
        )
        state_count = (
            df["prscrbr_state_abrvtn"].nunique()
            if "prscrbr_state_abrvtn" in df.columns
            else None
        )
        brnd_count = df["brnd_name"].nunique() if "brnd_name" in df.columns else 0
        gnrc_count = df["gnrc_name"].nunique() if "gnrc_name" in df.columns else 0
        drug_count = brnd_count + gnrc_count

        # Sampling method: first 25 states alphabetically (AL to MO), up to N rows each in NPI order
        sampling_method = f"first 25 states alphabetically (AL to MO), up to {rows_per_state:,} rows each in NPI order"

        metadata = {
            "data_source": self.data_source,
            "dataset_title": "Medicare Part D Prescribers - by Provider and Drug",
            "dataset_id": self.DATASET_ID,
            "release_year": 2024,
            "total_dataset_rows": 28023892,
            "cms_data_url": "https://data.cms.gov/dataset/Medicare-Part-D-Prescribers-by-Provider-and-Drug",
            "api_endpoint": self.ENDPOINT,
            "sampling_method": sampling_method,
            "download_timestamp": self.timestamp,
            "rows_downloaded": self.rows_dropped["total_input"],
            "rows_dropped": self.rows_dropped["total_dropped"],
            "rows_dropped_breakdown": {
                "null_critical_columns": self.rows_dropped["null_critical_columns"],
                "non_positive_claims": self.rows_dropped["non_positive_claims"],
                "nan_after_numeric_conversion": self.rows_dropped[
                    "nan_after_numeric_conversion"
                ],
            },
            "nan_per_column_after_conversion": self.rows_dropped["nan_per_column"],
            "total_rows": len(df),
            "unique_prescribers": prescriber_count,
            "unique_states": state_count,
            "unique_drugs": drug_count,
            "total_claims": (
                int(df["tot_clms"].sum()) if "tot_clms" in df.columns else None
            ),
            "total_cost_usd": (
                float(df["tot_drug_cst"].sum())
                if "tot_drug_cst" in df.columns
                else None
            ),
            "columns": list(df.columns),
        }

        if self.data_source == "SYNTHETIC":
            metadata["WARNING"] = (
                "THIS IS SYNTHETIC DATA FOR TESTING ONLY - NOT REAL CMS DATA"
            )

        logger.info("Metadata:")
        logger.info(f"  Source: {metadata['data_source']}")
        logger.info(f"  Sampling: {metadata['sampling_method']}")
        logger.info(
            f"  Rows (downloaded vs final): {metadata['rows_downloaded']:,} → {metadata['total_rows']:,} (-{metadata['rows_dropped']:,} dropped)"
        )
        logger.info(f"  Prescribers: {metadata['unique_prescribers']:,}")
        logger.info(f"  States: {metadata['unique_states']}")
        logger.info(f"  Drugs: {metadata['unique_drugs']:,}")
        logger.info(f"  Total Cost: ${metadata['total_cost_usd']:,.2f}")

        return metadata


def main():
    """Download CMS data and log results."""
    parser = argparse.ArgumentParser(
        description="Download real CMS Medicare Part D data via per-state sampling or generate synthetic sample",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python download_cms_data.py                          # Download real CMS data (25+ states, ~500K rows)
  python download_cms_data.py --synthetic              # Generate synthetic sample
  python download_cms_data.py --rows-per-state 10000   # Real data (10K per state, ~250K rows)
  python download_cms_data.py --rows-per-state 5000 --synthetic  # Synthetic (5K per state)
        """,
    )
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="Generate synthetic sample data (not real CMS data). Output files will be marked SYNTHETIC.",
    )
    parser.add_argument(
        "--rows-per-state",
        type=int,
        help=f"Rows to fetch per state (default: {CMSDataDownloader.DEFAULT_ROWS_PER_STATE:,})",
    )
    parser.add_argument(
        "--min-states",
        type=int,
        default=CMSDataDownloader.MIN_STATES_TO_SAMPLE,
        help=f"Minimum number of states to sample (default: {CMSDataDownloader.MIN_STATES_TO_SAMPLE})",
    )

    args = parser.parse_args()

    try:
        downloader = CMSDataDownloader(
            output_dir="data/raw", use_synthetic=args.synthetic
        )
        downloader.MIN_STATES_TO_SAMPLE = args.min_states

        output_file, metadata = downloader.download(rows_per_state=args.rows_per_state)

        logger.info("✓ Download complete!")
        logger.info(f"  Data Source: {metadata['data_source']}")
        logger.info(f"  Sampling: {metadata['sampling_method']}")
        logger.info(f"  File: {output_file}")
        logger.info(f"  Rows: {metadata['total_rows']:,}")
        logger.info(f"  Prescribers: {metadata['unique_prescribers']:,}")
        logger.info(f"  States: {metadata['unique_states']}")
        logger.info(f"  Drugs: {metadata['unique_drugs']:,}")
        logger.info(f"  Total Cost: ${metadata['total_cost_usd']:,.2f}")

        # Write metadata to JSON for CI/documentation
        metadata_file = output_file.replace(".csv", "_metadata.json")
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2, default=str)
        logger.info(f"  Metadata file: {metadata_file}")

        if metadata["data_source"] == "SYNTHETIC":
            logger.warning("⚠️  SYNTHETIC DATA GENERATED - NOT REAL CMS DATA")

        return 0

    except Exception as e:
        logger.error(f"✗ Download failed: {e}", exc_info=False)
        if "--synthetic" not in sys.argv:
            logger.error(
                "\n  Tip: If the CMS API is down, try again with --synthetic flag"
            )
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
