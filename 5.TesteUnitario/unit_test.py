import datetime
import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "4.DataQuality" / "script_data_quality.py"
SPEC = importlib.util.spec_from_file_location("script_data_quality", MODULE_PATH)
script_data_quality = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(script_data_quality)


class ScriptDataQualityTests(unittest.TestCase):
    def test_parse_date_returns_date_for_valid_string(self):
        self.assertEqual(
            script_data_quality.parse_date("2024-05-10"),
            datetime.date(2024, 5, 10),
        )

    def test_parse_date_returns_none_for_empty_or_invalid_values(self):
        self.assertIsNone(script_data_quality.parse_date("   "))
        self.assertIsNone(script_data_quality.parse_date("not-a-date"))
        self.assertIsNone(script_data_quality.parse_date(None))

    def test_count_missing_fields_reports_expected_required_fields(self):
        row = {
            "cod_cliente": "1001",
            "nm_cliente": "",
            "dt_nascimento_cliente": "",
            "dt_atualizacao": "2024-01-15",
            "tp_pessoa": "PF",
            "vl_renda": "1500.50",
            "num_telefone_cliente": "(11)99999-9999",
            "anomesdia": "20240115",
        }

        missing = script_data_quality.count_missing_fields(row)

        self.assertIn("nm_cliente", missing)
        self.assertIn("dt_nascimento_cliente", missing)
        self.assertNotIn("cod_cliente", missing)
        self.assertNotIn("dt_atualizacao", missing)

    def test_normalize_phone_uses_preferred_column_and_falls_back(self):
        self.assertEqual(
            script_data_quality.normalize_phone({"num_telefone_cliente": "(11)99999-9999"}),
            "(11)99999-9999",
        )
        self.assertEqual(
            script_data_quality.normalize_phone({"telefone_cliente": "(21)88888-8888"}),
            "(21)88888-8888",
        )
        self.assertEqual(script_data_quality.normalize_phone({}), "")

    def test_infer_anomesdia_uses_update_date_or_returns_none(self):
        self.assertEqual(
            script_data_quality.infer_anomesdia({"dt_atualizacao": "2024-02-20"}),
            "20240220",
        )
        self.assertIsNone(script_data_quality.infer_anomesdia({"dt_atualizacao": "invalid"}))

    def test_read_records_raises_file_not_found_for_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            list(script_data_quality.read_records("arquivo_que_nao_existe.csv"))


if __name__ == "__main__":
    unittest.main()
