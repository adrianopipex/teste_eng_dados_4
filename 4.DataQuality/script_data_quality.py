import argparse
import csv
import datetime
import os
import re
from collections import Counter

PHONE_PATTERN = re.compile(r"^\(\d{2}\)\d{5}-\d{4}$")
DATE_FORMAT = "%Y-%m-%d"
ANOMESDIA_PATTERN = re.compile(r"^\d{8}$")
VALID_PERSON_TYPES = {"PF", "PJ"}

REQUIRED_FIELDS = [
    "cod_cliente",
    "nm_cliente",
    "dt_nascimento_cliente",
    "dt_atualizacao",
    "tp_pessoa",
    "vl_renda",
    "num_telefone_cliente",
    "anomesdia",
]

MAX_SAMPLE_ERRORS = 10


def parse_args():
    parser = argparse.ArgumentParser(
        description="Valida qualidade de dados do dataset de clientes (Silver layer)."
    )
    parser.add_argument(
        "--input-path",
        default="datasets/clientes_sinteticos.csv",
        help="Caminho para o arquivo CSV de entrada.",
    )
    parser.add_argument(
        "--output-report",
        default="4.DataQuality/data_quality_report.txt",
        help="Caminho para o arquivo de relatório de saída.",
    )
    return parser.parse_args()


def parse_date(value):
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        return None


def is_uppercase_name(value):
    if value is None:
        return False
    stripped = value.strip()
    return bool(stripped) and stripped == stripped.upper()


def normalize_phone(row):
    if "num_telefone_cliente" in row and row["num_telefone_cliente"] is not None:
        return row["num_telefone_cliente"].strip()
    if "telefone_cliente" in row and row["telefone_cliente"] is not None:
        return row["telefone_cliente"].strip()
    return ""


def infer_anomesdia(row):
    dt_atualizacao = parse_date(row.get("dt_atualizacao", ""))
    if dt_atualizacao:
        return dt_atualizacao.strftime("%Y%m%d")
    return None


def read_records(input_path):
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Arquivo não encontrado: {input_path}")

    with open(input_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=",")
        for row in reader:
            yield row


def count_missing_fields(row):
    missing = []
    for field in REQUIRED_FIELDS:
        value = row.get(field, "")
        if value is None or not str(value).strip():
            missing.append(field)
    return missing


def build_report(metrics):
    lines = []
    lines.append("RELATÓRIO DE QUALIDADE DE DADOS - SILVER LAYER")
    lines.append("=" * 50)
    lines.append(f"Data de execução: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}")
    lines.append("")
    lines.append("1. Resumo geral")
    lines.append(f"- Registros lidos: {metrics['total_records']}")
    lines.append(f"- Registros válidos: {metrics['total_valid_records']}")
    lines.append(f"- Registros com alguma falha: {metrics['total_records'] - metrics['total_valid_records']}")
    lines.append("")
    lines.append("2. Campos obrigatórios")

    for field in REQUIRED_FIELDS:
        count = metrics["missing_required_fields"].get(field, 0)
        pct = (count / metrics["total_records"] * 100) if metrics["total_records"] else 0
        lines.append(f"- {field}: {count} registros ausentes ({pct:.1f}%)")

    lines.append("")
    lines.append("3. Consistência de chave e duplicidade")
    lines.append(f"- Clientes duplicados (cod_cliente): {metrics['duplicate_cod_cliente']}")
    lines.append("")
    lines.append("4. Validações de formato")
    lines.append(f"- Telefones no formato esperado (NN)NNNNN-NNNN: {metrics['valid_phone_count']} válidos, {metrics['invalid_phone_count']} inválidos")
    lines.append(f"- Nomes em maiúsculas: {metrics['uppercase_name_count']} válidos, {metrics['non_uppercase_name_count']} inválidos")
    lines.append(f"- Tipos de pessoa válidos (PF, PJ): {metrics['valid_person_type_count']} válidos, {metrics['invalid_person_type_count']} inválidos")
    lines.append(f"- Datas de atualização válidas: {metrics['valid_dt_atualizacao_count']} válidas, {metrics['invalid_dt_atualizacao_count']} inválidas")
    lines.append(f"- Data de nascimento válidas: {metrics['valid_birthdate_count']} válidas, {metrics['invalid_birthdate_count']} inválidas")
    lines.append(f"- Salários com valor numérico e não negativo: {metrics['valid_salary_count']} válidos, {metrics['invalid_salary_count']} inválidos")
    lines.append(f"- Partição anomesdia com formato YYYYMMDD: {metrics['valid_anomesdia_count']} válidos, {metrics['invalid_anomesdia_count']} inválidos")
    lines.append("")
    lines.append("5. Observações")
    if metrics["missing_anomesdia_records"]:
        lines.append("- O campo 'anomesdia' está ausente em registros de entrada. Ele é esperado na camada Silver como partição lógica/física.")
    if metrics["source_phone_column_present"]:
        lines.append("- O dataset de origem contém 'telefone_cliente'. No Silver, o campo esperado é 'num_telefone_cliente'.")
    if metrics["valid_records_without_errors"] == metrics["total_records"]:
        lines.append("- Todos os registros passaram em todas as validações implementadas.")
    else:
        lines.append("- Alguns registros apresentaram problemas de qualidade que precisam de correção antes da carga Silver.")

    if metrics["sample_errors"]:
        lines.append("")
        lines.append("6. Exemplos de registros com problemas")
        for sample in metrics["sample_errors"]:
            lines.append(sample)

    return "\n".join(lines)


def main():
    args = parse_args()

    metrics = {
        "total_records": 0,
        "total_valid_records": 0,
        "duplicate_cod_cliente": 0,
        "valid_phone_count": 0,
        "invalid_phone_count": 0,
        "uppercase_name_count": 0,
        "non_uppercase_name_count": 0,
        "valid_person_type_count": 0,
        "invalid_person_type_count": 0,
        "valid_dt_atualizacao_count": 0,
        "invalid_dt_atualizacao_count": 0,
        "valid_birthdate_count": 0,
        "invalid_birthdate_count": 0,
        "valid_salary_count": 0,
        "invalid_salary_count": 0,
        "valid_anomesdia_count": 0,
        "invalid_anomesdia_count": 0,
        "missing_required_fields": Counter(),
        "code_counts": Counter(),
        "sample_errors": [],
        "missing_anomesdia_records": False,
        "source_phone_column_present": False,
        "valid_records_without_errors": 0,
    }

    for idx, original_row in enumerate(read_records(args.input_path), start=1):
        metrics["total_records"] += 1
        row = {k: (v.strip() if isinstance(v, str) else v) for k, v in original_row.items()}

        if "telefone_cliente" in row and row.get("telefone_cliente", ""):
            metrics["source_phone_column_present"] = True
        if "num_telefone_cliente" not in row:
            row["num_telefone_cliente"] = row.get("telefone_cliente", "")

        anomesdia = row.get("anomesdia", "")
        if not anomesdia:
            inferred = infer_anomesdia(row)
            if inferred:
                row["anomesdia"] = inferred
            else:
                metrics["missing_anomesdia_records"] = True

        missing_fields = count_missing_fields(row)
        for field in missing_fields:
            metrics["missing_required_fields"][field] += 1

        cod_cliente = row.get("cod_cliente", "").strip()
        metrics["code_counts"][cod_cliente] += 1

        phone_value = normalize_phone(row)
        if PHONE_PATTERN.match(phone_value):
            metrics["valid_phone_count"] += 1
        else:
            metrics["invalid_phone_count"] += 1

        name_value = row.get("nm_cliente", "")
        if is_uppercase_name(name_value):
            metrics["uppercase_name_count"] += 1
        else:
            metrics["non_uppercase_name_count"] += 1

        tp_pessoa = row.get("tp_pessoa", "").upper()
        if tp_pessoa in VALID_PERSON_TYPES:
            metrics["valid_person_type_count"] += 1
        else:
            metrics["invalid_person_type_count"] += 1

        dt_atualizacao = parse_date(row.get("dt_atualizacao", ""))
        if dt_atualizacao:
            metrics["valid_dt_atualizacao_count"] += 1
        else:
            metrics["invalid_dt_atualizacao_count"] += 1

        dt_nascimento = parse_date(row.get("dt_nascimento_cliente", ""))
        if dt_nascimento and dt_nascimento <= datetime.date.today():
            metrics["valid_birthdate_count"] += 1
        else:
            metrics["invalid_birthdate_count"] += 1

        try:
            salary = float(row.get("vl_renda", ""))
            valid_salary = salary >= 0
            if valid_salary:
                metrics["valid_salary_count"] += 1
            else:
                metrics["invalid_salary_count"] += 1
        except (ValueError, TypeError):
            valid_salary = False
            metrics["invalid_salary_count"] += 1

        anomesdia_value = row.get("anomesdia", "")
        valid_anomesdia = bool(anomesdia_value and ANOMESDIA_PATTERN.match(anomesdia_value))
        if valid_anomesdia:
            metrics["valid_anomesdia_count"] += 1
        else:
            metrics["invalid_anomesdia_count"] += 1

        valid_phone = bool(PHONE_PATTERN.match(phone_value))
        valid_name_uppercase = is_uppercase_name(name_value)
        valid_person_type = tp_pessoa in VALID_PERSON_TYPES
        valid_update_date = bool(dt_atualizacao)
        valid_birth_date = bool(dt_nascimento)

        record_has_issues = bool(
            missing_fields or
            not valid_phone or
            not valid_name_uppercase or
            not valid_person_type or
            not valid_update_date or
            not valid_birth_date or
            not valid_salary or
            not valid_anomesdia
        )

        if not record_has_issues:
            metrics["valid_records_without_errors"] += 1

        if record_has_issues and len(metrics["sample_errors"]) < MAX_SAMPLE_ERRORS:
            metrics["sample_errors"].append(
                f"Registro {idx}: campos ausentes {missing_fields}, telefone='{phone_value}', nome='{name_value}', tp_pessoa='{tp_pessoa}', dt_atualizacao='{row.get('dt_atualizacao', '')}', dt_nascimento_cliente='{row.get('dt_nascimento_cliente', '')}', vl_renda='{row.get('vl_renda', '')}', anomesdia='{anomesdia_value}'"
            )

    duplicate_count = sum(1 for value in metrics["code_counts"].values() if value > 1)
    metrics["duplicate_cod_cliente"] = duplicate_count
    metrics["total_valid_records"] = metrics["valid_records_without_errors"]

    report_text = build_report(metrics)

    os.makedirs(os.path.dirname(args.output_report), exist_ok=True)
    with open(args.output_report, "w", encoding="utf-8") as report_file:
        report_file.write(report_text)

    print(report_text)
    print(f"\nRelatório escrito em: {args.output_report}")


if __name__ == "__main__":
    main()
