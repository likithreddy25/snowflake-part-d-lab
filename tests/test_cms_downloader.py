"""
Unit tests for CMS Medicare Part D data downloader script (2024 dataset).
Tests cover: per-state API sampling, data validation, realism checks, and error handling.
"""

import pytest
import pandas as pd
import requests
from unittest.mock import patch, MagicMock
import json
from pathlib import Path
from datetime import datetime
from io import StringIO

# Import the downloader
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from download_cms_data import CMSDataDownloader


class TestCMSDataDownloaderPerState:
    """Test suite for per-state sampling strategy."""

    @pytest.fixture
    def downloader_real(self, tmp_path):
        """Fixture: real CMS data mode with per-state sampling."""
        return CMSDataDownloader(output_dir=str(tmp_path), use_synthetic=False)

    @pytest.fixture
    def downloader_synthetic(self, tmp_path):
        """Fixture: synthetic mode."""
        return CMSDataDownloader(output_dir=str(tmp_path), use_synthetic=True)

    def test_initialization_real(self, downloader_real):
        """Test downloader initialization in real mode."""
        assert downloader_real.output_dir.exists()
        assert downloader_real.use_synthetic is False
        assert downloader_real.data_source == 'REAL_CMS'
        assert downloader_real.DATASET_ID == '9552739e-3d05-4c1b-8eff-ecabf391e2e5'
        assert 'data-api' in downloader_real.ENDPOINT

    def test_initialization_synthetic(self, downloader_synthetic):
        """Test downloader initialization in synthetic mode."""
        assert downloader_synthetic.output_dir.exists()
        assert downloader_synthetic.use_synthetic is True
        assert downloader_synthetic.data_source == 'SYNTHETIC'

    def test_synthetic_data_generation(self, downloader_synthetic):
        """Test synthetic data generation with per-state structure."""
        df = downloader_synthetic._generate_synthetic_data(rows_per_state=100)
        assert df is not None
        assert len(df) >= 100
        assert 'Prscrbr_NPI' in df.columns
        assert 'Brnd_Name' in df.columns
        assert 'Prscrbr_State_Abrvtn' in df.columns

    @patch('requests.Session.get')
    def test_fetch_state_data_success(self, mock_get, downloader_real):
        """Test fetching data for a single state with correct CMS API request format."""
        # Mock JSON response (note: CMS API returns all columns as strings)
        mock_response_data = {
            'data': [
                {
                    'Prscrbr_NPI': '1234567890',
                    'Prscrbr_Last_Org_Name': 'County Hospital',
                    'Prscrbr_First_Name': 'John',
                    'Prscrbr_City': 'Boston',
                    'Prscrbr_State_Abrvtn': 'MA',
                    'Prscrbr_Type': 'MD',
                    'Brnd_Name': 'Metformin',
                    'Gnrc_Name': 'Metformin',
                    'Tot_Clms': '1000',
                    'Tot_30day_Fills': '1000',
                    'Tot_Day_Suply': '30000',
                    'Tot_Drug_Cst': '50000.00',
                    'Tot_Benes': '500',
                }
            ]
        }

        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        df = downloader_real._fetch_state_data('MA', rows_per_state=100)

        # Verify request format: filter[Prscrbr_State_Abrvtn]=MA&size=5000&offset=0
        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args[1]
        assert 'params' in call_kwargs
        params = call_kwargs['params']
        assert params['filter[Prscrbr_State_Abrvtn]'] == 'MA'
        assert params['size'] == 5000
        assert params['offset'] == 0

        assert df is not None
        assert len(df) == 1
        assert df.iloc[0]['Prscrbr_NPI'] == '1234567890'
        assert df.iloc[0]['Prscrbr_State_Abrvtn'] == 'MA'

    @patch('requests.Session.get')
    def test_fetch_state_data_pagination_offset_by_actual_returned(self, mock_get, downloader_real):
        """Test that offset advances by actual rows returned, not by requested size.

        CMS API may return fewer rows than requested (e.g., request size=5000, get 3500).
        Next request should use offset=3500, not offset=5000.
        Pagination continues until actual_returned < request_size (end of data).
        """
        # First request: returns 3500 rows (less than requested 5000)
        # This signals end of data, so pagination stops
        mock_response1 = MagicMock()
        mock_response1.json.return_value = {
            'data': [
                {
                    'Prscrbr_NPI': f'{1000000000 + i}',
                    'Prscrbr_Last_Org_Name': f'Org_{i}',
                    'Prscrbr_First_Name': f'Doctor_{i}',
                    'Prscrbr_City': 'City',
                    'Prscrbr_State_Abrvtn': 'CA',
                    'Prscrbr_Type': 'MD',
                    'Brnd_Name': 'Drug',
                    'Gnrc_Name': 'Generic',
                    'Tot_Clms': '100',
                    'Tot_30day_Fills': '100',
                    'Tot_Day_Suply': '3000',
                    'Tot_Drug_Cst': '5000',
                    'Tot_Benes': '50',
                }
                for i in range(3500)
            ]
        }
        mock_response1.status_code = 200
        mock_response1.raise_for_status = MagicMock()

        mock_get.return_value = mock_response1

        df = downloader_real._fetch_state_data('CA', rows_per_state=10000)
        assert len(df) == 3500

        # Should only make ONE request because actual_returned (3500) < request_size (5000)
        # This signals end of data for this state
        assert mock_get.call_count == 1

        first_call_params = mock_get.call_args[1]['params']
        assert first_call_params['offset'] == 0
        assert first_call_params['size'] == 5000
        assert first_call_params['filter[Prscrbr_State_Abrvtn]'] == 'CA'

    @patch('requests.Session.get')
    def test_fetch_state_data_multiple_pages_to_reach_target(self, mock_get, downloader_real):
        """Test pagination across multiple pages when needed to reach target rows.

        If API returns full page (5000 rows) and we need more, keep paginating.
        """
        # Create responses for 3 pages, each returning 5000 rows
        responses = []
        for page in range(3):
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                'data': [
                    {
                        'Prscrbr_NPI': f'{1000000000 + page * 5000 + i}',
                        'Prscrbr_Last_Org_Name': f'Org_{i}',
                        'Prscrbr_First_Name': f'Doctor_{i}',
                        'Prscrbr_City': 'City',
                        'Prscrbr_State_Abrvtn': 'TX',
                        'Prscrbr_Type': 'MD',
                        'Brnd_Name': 'Drug',
                        'Gnrc_Name': 'Generic',
                        'Tot_Clms': '100',
                        'Tot_30day_Fills': '100',
                        'Tot_Day_Suply': '3000',
                        'Tot_Drug_Cst': '5000',
                        'Tot_Benes': '50',
                    }
                    for i in range(5000)
                ]
            }
            mock_resp.status_code = 200
            mock_resp.raise_for_status = MagicMock()
            responses.append(mock_resp)

        # Fourth request returns 2000 rows (signals end)
        mock_resp_final = MagicMock()
        mock_resp_final.json.return_value = {
            'data': [
                {
                    'Prscrbr_NPI': f'{1000000000 + i}',
                    'Prscrbr_Last_Org_Name': f'Org_{i}',
                    'Prscrbr_First_Name': f'Doctor_{i}',
                    'Prscrbr_City': 'City',
                    'Prscrbr_State_Abrvtn': 'TX',
                    'Prscrbr_Type': 'MD',
                    'Brnd_Name': 'Drug',
                    'Gnrc_Name': 'Generic',
                    'Tot_Clms': '100',
                    'Tot_30day_Fills': '100',
                    'Tot_Day_Suply': '3000',
                    'Tot_Drug_Cst': '5000',
                    'Tot_Benes': '50',
                }
                for i in range(2000)
            ]
        }
        mock_resp_final.status_code = 200
        mock_resp_final.raise_for_status = MagicMock()
        responses.append(mock_resp_final)

        mock_get.side_effect = responses

        # Request 17000 rows, should get 17000 (5000+5000+5000+2000)
        df = downloader_real._fetch_state_data('TX', rows_per_state=17000)
        assert len(df) == 17000

        # Should make 4 API calls: 0, 5000, 10000, 15000 offsets
        assert mock_get.call_count == 4

        # Verify offsets increment by actual rows returned
        calls = mock_get.call_args_list
        assert calls[0][1]['params']['offset'] == 0
        assert calls[1][1]['params']['offset'] == 5000
        assert calls[2][1]['params']['offset'] == 10000
        assert calls[3][1]['params']['offset'] == 15000

    @patch('requests.Session.get')
    def test_fetch_state_data_no_data_for_state(self, mock_get, downloader_real):
        """Test handling when state has no data."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Not found")
        mock_get.return_value = mock_response

        result = downloader_real._fetch_state_data('XX', rows_per_state=100)
        assert result is None

    @patch('requests.Session.get')
    def test_fetch_via_state_sampling_multiple_states(self, mock_get, downloader_real):
        """Test per-state sampling combines data from multiple states."""
        # Mock data for first state
        mock_response_ma = MagicMock()
        mock_response_ma.json.return_value = {
            'data': [
                {
                    'Prscrbr_NPI': '1000000001',
                    'Prscrbr_Last_Org_Name': 'MA Org',
                    'Prscrbr_First_Name': 'John',
                    'Prscrbr_City': 'Boston',
                    'Prscrbr_State_Abrvtn': 'MA',
                    'Prscrbr_Type': 'MD',
                    'Brnd_Name': 'Metformin',
                    'Gnrc_Name': 'Metformin',
                    'Tot_Clms': '1000',
                    'Tot_30day_Fills': '1000',
                    'Tot_Day_Suply': '30000',
                    'Tot_Drug_Cst': '50000',
                    'Tot_Benes': '500',
                }
            ]
        }
        mock_response_ma.status_code = 200
        mock_response_ma.raise_for_status = MagicMock()

        # Mock data for second state
        mock_response_ca = MagicMock()
        mock_response_ca.json.return_value = {
            'data': [
                {
                    'Prscrbr_NPI': '1000000002',
                    'Prscrbr_Last_Org_Name': 'CA Org',
                    'Prscrbr_First_Name': 'Jane',
                    'Prscrbr_City': 'SF',
                    'Prscrbr_State_Abrvtn': 'CA',
                    'Prscrbr_Type': 'MD',
                    'Brnd_Name': 'Lisinopril',
                    'Gnrc_Name': 'Lisinopril',
                    'Tot_Clms': '2000',
                    'Tot_30day_Fills': '2000',
                    'Tot_Day_Suply': '60000',
                    'Tot_Drug_Cst': '100000',
                    'Tot_Benes': '1000',
                }
            ]
        }
        mock_response_ca.status_code = 200
        mock_response_ca.raise_for_status = MagicMock()

        mock_get.side_effect = [mock_response_ma, mock_response_ca] + [mock_response_ma] * 50

        df = downloader_real._fetch_via_state_sampling(rows_per_state=10)
        assert df is not None
        assert len(df) >= 2
        assert df['Prscrbr_State_Abrvtn'].nunique() >= 2

    def test_validation_and_cleaning_real_columns(self, downloader_real):
        """Test data validation with real 2024 CMS column names (all strings)."""
        raw_data = pd.DataFrame({
            'Prscrbr_NPI': ['1234567890', '1234567891', '1234567892', None],
            'Prscrbr_State_Abrvtn': ['MA', 'CA', None, 'NY'],
            'Brnd_Name': ['Metformin', 'Lisinopril', 'Atorvastatin', 'Metformin'],
            'Tot_Clms': ['100', '-50', '0', '200'],  # String values from API
            'Tot_Drug_Cst': ['5000.0', '3000.0', '1000.0', '8000.0'],
            'Gnrc_Name': ['Met', 'Lis', 'Ator', 'Met'],
        })

        cleaned = downloader_real._validate_and_clean(raw_data)

        # Should remove row with negative claim count
        assert len(cleaned) < len(raw_data)
        # Should remove rows with nulls in critical columns
        assert cleaned['prscrbr_npi'].notna().all()
        assert cleaned['prscrbr_state_abrvtn'].notna().all()

    def test_column_case_normalization(self, downloader_real):
        """Test that CMS column names are normalized to lowercase."""
        raw_data = pd.DataFrame({
            'Prscrbr_NPI': ['1', '2'],
            'Prscrbr_State_Abrvtn': ['MA', 'CA'],
            'Brnd_Name': ['Drug A', 'Drug B'],
            'Tot_Clms': ['100', '200'],
            'Tot_Drug_Cst': ['5000', '10000'],
            'Gnrc_Name': ['Generic A', 'Generic B'],
        })

        cleaned = downloader_real._validate_and_clean(raw_data)
        # Columns should be converted to lowercase
        assert all(col.islower() or '_' in col for col in cleaned.columns)
        assert 'prscrbr_npi' in cleaned.columns
        assert 'prscrbr_state_abrvtn' in cleaned.columns

    def test_positive_claims_only(self, downloader_real):
        """Test that rows with zero/negative claims are filtered."""
        raw_data = pd.DataFrame({
            'Prscrbr_NPI': ['1', '2', '3'],
            'Prscrbr_State_Abrvtn': ['MA', 'MA', 'MA'],
            'Brnd_Name': ['A', 'B', 'C'],
            'Tot_Clms': ['100', '0', '-50'],
            'Tot_Drug_Cst': ['5000', '0', '1000'],
            'Gnrc_Name': ['A', 'B', 'C'],
        })

        cleaned = downloader_real._validate_and_clean(raw_data)
        # Only row with positive claims should remain
        assert len(cleaned) == 1
        assert cleaned.iloc[0]['tot_clms'] == 100

    def test_data_realism_validation_passes(self, downloader_real):
        """Test that realistic data passes validation."""
        prescriber_count = 5000
        state_count = 50
        drug_count = 1000

        # Should not raise
        downloader_real._validate_data_realism(prescriber_count, state_count, drug_count)

    def test_data_realism_validation_fails_few_prescribers(self, downloader_real):
        """Test that few prescribers triggers realism check failure."""
        with pytest.raises(RuntimeError, match="Too few prescribers"):
            downloader_real._validate_data_realism(
                prescriber_count=100,  # Too few
                state_count=50,
                drug_count=1000
            )

    def test_data_realism_validation_fails_few_states(self, downloader_real):
        """Test that few states triggers realism check failure."""
        with pytest.raises(RuntimeError, match="Too few states"):
            downloader_real._validate_data_realism(
                prescriber_count=5000,
                state_count=4,  # Too few
                drug_count=1000
            )

    def test_data_realism_validation_fails_few_drugs(self, downloader_real):
        """Test that few drugs triggers realism check failure."""
        with pytest.raises(RuntimeError, match="Too few drugs"):
            downloader_real._validate_data_realism(
                prescriber_count=5000,
                state_count=50,
                drug_count=10  # Too few
            )

    def test_download_synthetic_creates_csv_with_synthetic_marker(self, downloader_synthetic):
        """Test that synthetic download creates CSV with SYNTHETIC marker."""
        output_file, metadata = downloader_synthetic.download(rows_per_state=10)

        # Should have created a CSV file with SYNTHETIC marker
        assert 'SYNTHETIC' in output_file
        assert output_file.endswith('_SYNTHETIC.csv')
        assert Path(output_file).exists()
        assert metadata['total_rows'] >= 10
        assert metadata['data_source'] == 'SYNTHETIC'
        assert 'WARNING' in metadata

    def test_download_synthetic_metadata_includes_warning(self, downloader_synthetic):
        """Test that synthetic metadata includes WARNING."""
        output_file, metadata = downloader_synthetic.download(rows_per_state=10)

        assert metadata['data_source'] == 'SYNTHETIC'
        assert 'WARNING' in metadata
        assert 'NOT REAL CMS DATA' in metadata['WARNING']

    def test_metadata_computation_real(self, downloader_real):
        """Test metadata computation for real CMS mode."""
        test_data = pd.DataFrame({
            'prscrbr_npi': ['1', '2', '3', '3'],
            'prscrbr_state_abrvtn': ['MA', 'MA', 'CA', 'CA'],
            'brnd_name': ['Drug A', 'Drug B', 'Drug C', 'Drug C'],
            'gnrc_name': ['Gen A', 'Gen B', 'Gen C', 'Gen C'],
            'tot_clms': [100, 200, 150, 50],
            'tot_drug_cst': [5000.0, 10000.0, 7500.0, 2500.0],
        })

        metadata = downloader_real._compute_metadata(test_data, rows_per_state=5000)

        assert metadata['data_source'] == 'REAL_CMS'
        assert metadata['total_rows'] == 4
        assert metadata['unique_prescribers'] == 3
        assert metadata['unique_states'] == 2
        # Drug count includes unique brand + unique generic names
        assert metadata['unique_drugs'] == 6  # 3 unique brand + 3 unique generic
        assert metadata['total_claims'] == 500
        assert metadata['total_cost_usd'] == 25000.0
        assert 'WARNING' not in metadata
        assert metadata['dataset_id'] == '9552739e-3d05-4c1b-8eff-ecabf391e2e5'
        assert metadata['release_year'] == 2024
        assert 'first 25 states alphabetically' in metadata['sampling_method']
        assert 'AL to MO' in metadata['sampling_method']
        assert 'NPI order' in metadata['sampling_method']

    def test_metadata_computation_synthetic(self, downloader_synthetic):
        """Test metadata computation for synthetic mode."""
        test_data = pd.DataFrame({
            'prscrbr_npi': ['1', '2', '3', '3'],
            'prscrbr_state_abrvtn': ['MA', 'MA', 'CA', 'CA'],
            'brnd_name': ['Drug A', 'Drug B', 'Drug C', 'Drug C'],
            'gnrc_name': ['Gen A', 'Gen B', 'Gen C', 'Gen C'],
            'tot_clms': [100, 200, 150, 50],
            'tot_drug_cst': [5000.0, 10000.0, 7500.0, 2500.0],
        })

        metadata = downloader_synthetic._compute_metadata(test_data, rows_per_state=5000)

        assert metadata['data_source'] == 'SYNTHETIC'
        assert 'WARNING' in metadata
        assert 'NOT REAL CMS DATA' in metadata['WARNING']

    def test_synthetic_data_has_geographic_diversity(self, downloader_synthetic):
        """Test that synthetic data spans multiple states."""
        df = downloader_synthetic._generate_synthetic_data(rows_per_state=5000)

        state_count = df['Prscrbr_State_Abrvtn'].nunique()
        # Should have data from many states
        assert state_count >= 20, f"Synthetic data has only {state_count} states"

    def test_api_2024_dataset_id_correct(self, downloader_real):
        """Test that the 2024 dataset ID is correct."""
        assert downloader_real.DATASET_ID == '9552739e-3d05-4c1b-8eff-ecabf391e2e5'
        assert 'data-api' in downloader_real.ENDPOINT
        assert '9552739e-3d05-4c1b-8eff-ecabf391e2e5' in downloader_real.ENDPOINT

    def test_api_respects_max_page_size(self, downloader_real):
        """Test that downloader respects CMS API's max page size."""
        assert downloader_real.MAX_PAGE_SIZE == 50000
        assert downloader_real.POLITE_DELAY_SECONDS > 0

    def test_rows_dropped_breakdown_sums_correctly(self, downloader_real):
        """Test that row drop breakdown sums to total input minus total output.

        Note: Tot_Benes is nullable (CMS suppression), so NaN in it doesn't drop rows.
        """
        # Create test data with various quality issues
        test_data = pd.DataFrame({
            'Prscrbr_NPI': ['1', '2', None, '4', '5', '6', '7'],
            'Prscrbr_Last_Org_Name': ['A', 'B', 'C', 'D', 'E', 'F', 'G'],
            'Prscrbr_First_Name': ['a', 'b', 'c', 'd', 'e', 'f', 'g'],
            'Prscrbr_City': ['x', 'y', 'z', 'x', 'y', 'z', 'x'],
            'Prscrbr_State_Abrvtn': ['CA', 'CA', None, 'NY', 'NY', 'NY', 'TX'],
            'Prscrbr_Type': ['MD', 'MD', 'MD', 'MD', 'MD', 'MD', 'MD'],
            'Brnd_Name': ['Drug', 'Drug', 'Drug', None, 'Drug', 'Drug', 'Drug'],
            'Gnrc_Name': ['Gen', 'Gen', 'Gen', 'Gen', 'Gen', 'Gen', 'Gen'],
            'Tot_Clms': ['100', '200', '50', '300', '-50', '0', '150'],  # Issues at rows 2,4,5
            'Tot_30day_Fills': ['100', '200', '50', '300', '50', '0', '150'],
            'Tot_Day_Suply': ['3000', '6000', '1500', '9000', '1500', '0', '4500'],
            'Tot_Drug_Cst': ['5000', '10000', '2500', '15000', '2500', '0', '7500'],
            'Tot_Benes': ['50', '100', None, '150', '25', None, '75'],  # Suppressed (None) but kept
        })

        initial_count = len(test_data)
        cleaned = downloader_real._validate_and_clean(test_data)
        final_count = len(cleaned)

        # Verify breakdown is measured correctly
        breakdown = downloader_real.rows_dropped

        # Sum of all drops should equal input - output
        total_dropped_measured = (
            breakdown['null_critical_columns'] +
            breakdown['non_positive_claims'] +
            breakdown['nan_after_numeric_conversion']
        )
        expected_dropped = initial_count - final_count

        assert total_dropped_measured == expected_dropped, (
            f"Breakdown sum {total_dropped_measured} != "
            f"input {initial_count} - output {final_count} = {expected_dropped}"
        )

        # Verify all breakdowns are non-negative
        assert breakdown['null_critical_columns'] >= 0
        assert breakdown['non_positive_claims'] >= 0
        assert breakdown['nan_after_numeric_conversion'] >= 0
        assert breakdown['total_dropped'] >= 0
        assert breakdown['total_dropped'] == total_dropped_measured

    def test_tot_benes_nullable_not_dropped(self, downloader_real):
        """Test that Tot_Benes NaN (CMS suppression for <11 beneficiaries) doesn't drop rows."""
        # Data with Tot_Benes blank (CMS suppression)
        test_data = pd.DataFrame({
            'Prscrbr_NPI': ['1', '2', '3'],
            'Prscrbr_Last_Org_Name': ['A', 'B', 'C'],
            'Prscrbr_First_Name': ['a', 'b', 'c'],
            'Prscrbr_City': ['x', 'y', 'z'],
            'Prscrbr_State_Abrvtn': ['CA', 'CA', 'CA'],
            'Prscrbr_Type': ['MD', 'MD', 'MD'],
            'Brnd_Name': ['Drug', 'Drug', 'Drug'],
            'Gnrc_Name': ['Gen', 'Gen', 'Gen'],
            'Tot_Clms': ['100', '200', '300'],
            'Tot_30day_Fills': ['100', '200', '300'],
            'Tot_Day_Suply': ['3000', '6000', '9000'],
            'Tot_Drug_Cst': ['5000', '10000', '15000'],
            'Tot_Benes': ['50', None, None],  # Some suppressed
        })

        cleaned = downloader_real._validate_and_clean(test_data)

        # All 3 rows should survive (Tot_Benes is nullable)
        assert len(cleaned) == 3
        # tot_benes column should have NaN preserved
        assert cleaned['tot_benes'].isna().sum() == 2

    def test_nan_per_column_tracked(self, downloader_real):
        """Test that NaN counts are tracked per column after conversion."""
        test_data = pd.DataFrame({
            'Prscrbr_NPI': ['1', 'invalid', '3'],
            'Prscrbr_Last_Org_Name': ['A', 'B', 'C'],
            'Prscrbr_First_Name': ['a', 'b', 'c'],
            'Prscrbr_City': ['x', 'y', 'z'],
            'Prscrbr_State_Abrvtn': ['CA', 'CA', 'CA'],
            'Prscrbr_Type': ['MD', 'MD', 'MD'],
            'Brnd_Name': ['Drug', 'Drug', 'Drug'],
            'Gnrc_Name': ['Gen', 'Gen', 'Gen'],
            'Tot_Clms': ['100', '200', '300'],
            'Tot_30day_Fills': ['100', '200', '300'],
            'Tot_Day_Suply': ['3000', '6000', '9000'],
            'Tot_Drug_Cst': ['5000', 'bad_cost', '15000'],
            'Tot_Benes': ['50', '100', None],
        })

        downloader_real._validate_and_clean(test_data)
        nan_per_col = downloader_real.rows_dropped['nan_per_column']

        # Should track NaN in prscrbr_npi and tot_drug_cst (conversion errors)
        # and tot_benes (suppression)
        assert 'prscrbr_npi' in nan_per_col
        assert 'tot_drug_cst' in nan_per_col
        assert nan_per_col['prscrbr_npi'] > 0
        assert nan_per_col['tot_drug_cst'] > 0

    @patch('requests.Session.get')
    def test_api_request_format_uses_query_parameters_not_json_filter(self, mock_get, downloader_real):
        """
        Test that API requests use correct format with query parameters.
        CORRECT:   filter[Prscrbr_State_Abrvtn]=AL&size=5000&offset=0
        WRONG:     filter=[{"property": "...", "value": "..."}]&limit=5000
        """
        mock_response = MagicMock()
        mock_response.json.return_value = {'data': []}
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        # Make a fetch call
        downloader_real._fetch_state_data('NY', rows_per_state=5000)

        # Verify the exact request format
        mock_get.assert_called_once()
        call_args = mock_get.call_args

        # Check URL is correct
        assert downloader_real.ENDPOINT in call_args[0][0]

        # Check query parameters
        params = call_args[1]['params']
        assert params['filter[Prscrbr_State_Abrvtn]'] == 'NY', "Must use filter[Prscrbr_State_Abrvtn]=XX format"
        assert params['size'] == 5000, "Must use 'size' parameter, not 'limit'"
        assert params['offset'] == 0, "Must use 'offset' parameter"

        # Ensure WRONG formats are NOT used
        param_str = str(params)
        assert '{"property"' not in param_str, "Must NOT use JSON filter array"
        assert 'limit' not in params, "Must NOT use 'limit' parameter"

    @pytest.mark.integration
    @pytest.mark.skip(reason="Integration test: makes real API call. Run with: pytest tests/test_cms_downloader.py::TestCMSDataDownloaderPerState::test_real_api_call_single_state -v")
    def test_real_api_call_single_state(self):
        """
        Integration test: Make a real API call with size=3 to verify the endpoint works.

        This test is SKIPPED BY DEFAULT. Enable with:
          pytest tests/test_cms_downloader.py::TestCMSDataDownloaderPerState::test_real_api_call_single_state -v

        Tests that:
          1. API is reachable at the documented endpoint
          2. Query parameters work correctly
          3. Response contains expected columns
          4. All rows have correct state
        """
        downloader = CMSDataDownloader(use_synthetic=False)

        # Request just 3 rows to keep test fast
        df = downloader._fetch_state_data('AL', rows_per_state=3)

        # Should get data (Alabama always has prescriber data)
        assert df is not None
        assert len(df) <= 3, "Should get at most 3 rows"

        # All rows should have correct state
        assert (df['Prscrbr_State_Abrvtn'] == 'AL').all(), "All rows must be from AL"

        # Should have expected columns
        required_cols = ['Prscrbr_NPI', 'Prscrbr_State_Abrvtn', 'Brnd_Name', 'Tot_Clms']
        for col in required_cols:
            assert col in df.columns, f"Missing column: {col}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
